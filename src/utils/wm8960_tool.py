#!/usr/bin/env python3
import glob
import os
import sys
import subprocess
from smbus2 import SMBus, i2c_msg

WM8960_ADDR = 0x1A  # default; can be overridden at runtime

HELP_TEXT = """Commands:
  list                     - list loaded registers with current values
  set <idx> <value>        - set register at list index to value (hex or dec)
  write <idx>              - write the current value of register at index
  writeall                 - write all registers in the list
  writeaddr <addr> <val>   - direct write by register address (hex or dec)
  setaddr <addr> <val>     - update cached value by register address
  macro <name>             - run a predefined write sequence
  help                     - show this help
  quit / exit              - leave the tool

Register file format (txt):
  Each non-comment line: <addr> [NAME] [default]
  Examples:
    0x00 LEFT_IN_VOL 0x017
    0x02 LOUT1_VOL 0x079
  Comments and blank lines are ignored.
"""


def discover_i2c_buses():
    """Return sorted list of numeric I2C bus IDs discovered under /dev."""
    buses = []
    for path in glob.glob("/dev/i2c-*"):
        try:
            buses.append(int(path.rsplit("-", 1)[1]))
        except ValueError:
            continue
    return sorted(set(buses))


def probe_bus_for_wm8960(bus_num: int) -> str:
    """Lightweight probe for WM8960 address on a given bus; returns a hint string."""
    try:
        with SMBus(bus_num) as bus:
            for addr in (0x1A, 0x1B):
                try:
                    # Use SMBus quick write for presence detection (matches i2cdetect).
                    bus.write_quick(addr)
                    return f"(device responded at 0x{addr:02x})"
                except OSError:
                    continue
    except PermissionError:
        return "(no access; try sudo or add user to i2c group)"
    except FileNotFoundError:
        return "(not present)"
    return ""


def list_usb_devices():
    """Return lsusb output as list of lines."""
    try:
        out = subprocess.run(
            ["lsusb"], check=True, capture_output=True, text=True
        ).stdout.splitlines()
        return [line.strip() for line in out if line.strip()]
    except Exception as exc:  # pragma: no cover - env-specific
        print(f"Could not list USB devices: {exc}", file=sys.stderr)
        return []


def choose_usb_device():
    usb_devices = list_usb_devices()
    if not usb_devices:
        print("No USB devices found (or lsusb unavailable).")
        return None

    print("USB devices (pick your USB-I2C adapter):")
    for idx, line in enumerate(usb_devices):
        print(f"  [{idx}] {line}")
    choice = input(f"Select USB device [0-{len(usb_devices) - 1}] (default 0): ").strip()
    if choice == "":
        return usb_devices[0]
    try:
        return usb_devices[int(choice)]
    except (ValueError, IndexError):
        print("Invalid selection.", file=sys.stderr)
        sys.exit(1)


def scan_bus(bus_num: int):
    """
    Rough equivalent of `i2cdetect -y <bus>`.
    Uses SMBus quick write to test for ACK; prints a 16x16 grid.
    """
    print(f"\nScanning /dev/i2c-{bus_num} for devices (ACK test)...")
    header = "     " + " ".join(f"{col:x}" for col in range(16))
    print(header)
    try:
        with SMBus(bus_num) as bus:
            for row in range(8):  # 0x00-0x7f valid 7-bit addresses
                base = row * 16
                line = f"{base:02x}: "
                for col in range(16):
                    addr = base + col
                    if addr < 0x03 or addr > 0x77:
                        line += "   "
                        continue
                    try:
                        # Presence check; avoids writing data to device registers.
                        bus.write_quick(addr)
                        line += f"{addr:02x} "
                    except OSError:
                        line += "-- "
                print(line.rstrip())
    except PermissionError:
        print("Permission denied opening the bus; try sudo or add user to i2c group.")
    except FileNotFoundError:
        print(f"/dev/i2c-{bus_num} not found.")


def list_i2c_adapters():
    """
    Return a list of (bus_num, description) tuples.
    Uses `i2cdetect -l` when available; falls back to /dev/i2c-*.
    """
    adapters = []
    try:
        out = subprocess.run(
            ["i2cdetect", "-l"], check=True, capture_output=True, text=True
        ).stdout.splitlines()
        for line in out:
            parts = line.split()
            if not parts:
                continue
            # Expect format: i2c-<n> <type> <name> <algo>
            bus_token = parts[0]
            if bus_token.startswith("i2c-"):
                try:
                    num = int(bus_token.split("-")[1])
                    desc = " ".join(parts[1:]) if len(parts) > 1 else ""
                    adapters.append((num, desc))
                except ValueError:
                    continue
    except Exception:
        # Fallback to discover_i2c_buses with empty descriptions.
        adapters = [(n, "") for n in discover_i2c_buses()]
    return sorted(adapters, key=lambda t: t[0])


def choose_bus():
    # First, let the user pick the USB-I2C adapter to orient themselves.
    chosen_usb = choose_usb_device()
    if chosen_usb:
        print(f"Selected USB device: {chosen_usb}")

    adapters = list_i2c_adapters()
    if not adapters:
        print("No /dev/i2c-* adapters found.", file=sys.stderr)
        sys.exit(1)

    print("Available I2C adapters:")
    for idx, (num, desc) in enumerate(adapters):
        print(f"  [{idx}] /dev/i2c-{num}  {desc}")

    print("Scanning I2C buses for WM8960 (0x1a/0x1b)...")
    responding = []
    for num, _ in adapters:
        tag = probe_bus_for_wm8960(num)
        if "device responded" in tag:
            responding.append(num)
            print(f"  /dev/i2c-{num} {tag}")
        elif tag:
            print(f"  /dev/i2c-{num} {tag}")

    if len(responding) == 1:
        bus_choice = responding[0]
        print(f"Using /dev/i2c-{bus_choice}.")
        return bus_choice
    if len(responding) > 1:
        print("Multiple buses responded; pick one:")
        for idx, num in enumerate(responding):
            print(f"  [{idx}] /dev/i2c-{num}")
        choice = input(
            f"Select bus by index or number [0-{len(responding) - 1}] (default 0): "
        ).strip()
        if choice == "":
            return responding[0]
        try:
            # Allow either index or explicit bus number.
            if choice.isdigit() and int(choice) < len(responding):
                return responding[int(choice)]
            return int(choice)
        except (ValueError, IndexError):
            print("Invalid selection.", file=sys.stderr)
            sys.exit(1)

    # None responded; fall back to first bus or user input.
    default_bus = adapters[0][0]
    choice = input(
        f"No WM8960 detected. Enter I2C bus index or number to try (default {default_bus}): "
    ).strip()
    if choice == "":
        return default_bus
    try:
        if choice.isdigit():
            choice_idx = int(choice)
            if choice_idx < len(adapters):
                return adapters[choice_idx][0]
        return int(choice)
    except ValueError:
        print("Invalid selection.", file=sys.stderr)
        sys.exit(1)


def parse_register_file(path: str):
    """Parse a simple register definition file."""
    regs = []
    candidates = [path]
    if not os.path.isabs(path):
        candidates.append(os.path.join(os.path.dirname(__file__), path))

    opened = None
    for candidate in candidates:
        if os.path.isfile(candidate):
            opened = candidate
            break

    if opened is None:
        print(f"Register file not found: {path}", file=sys.stderr)
        return []

    try:
        with open(opened, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                parts = stripped.split()
                if not parts:
                    continue
                try:
                    addr = int(parts[0], 0)
                except ValueError:
                    print(f"Skipping line (bad addr): {line.strip()}")
                    continue
                name = parts[1] if len(parts) > 1 else f"REG_{addr:02X}"
                default = None
                if len(parts) > 2:
                    try:
                        default = int(parts[2], 0)
                    except ValueError:
                        pass
                regs.append(
                    {
                        "addr": addr,
                        "name": name,
                        "default": default,
                        "value": default if default is not None else 0,
                    }
                )
        print(f"Loaded register file: {opened}")
    except FileNotFoundError:
        print(f"Register file not found: {opened}", file=sys.stderr)
        return []
    return regs


# Predefined macros: name -> list of (addr, value, comment)
MACROS = {
    "hp_i2s_init": [
        (0x0F, 0x000, "Reset"),
        (0x19, 0x0C0, "Power1: VREF up + VMID=50k"),
        (0x1A, 0x1E0, "Power2: DACL/DACR + LOUT1/ROUT1 on"),
        (0x2F, 0x00C, "Power3: enable L/R output mixers"),
        (0x22, 0x100, "Route left DAC to left out mixer"),
        (0x25, 0x100, "Route right DAC to right out mixer"),
        (0x02, 0x179, "LOUT1 volume 0 dB, update"),
        (0x03, 0x179, "ROUT1 volume 0 dB, update"),
        (0x09, 0x0FF, "Left DAC volume 0 dB"),
        (0x0A, 0x0FF, "Right DAC volume 0 dB"),
        (0x05, 0x000, "Unmute DAC digital soft mute"),
        (0x07, 0x00E, "Audio IF: I2S slave, 32-bit (change for your width)"),
        (0x04, 0x000, "CLK1: SYSCLK from MCLK"),
    ],
}


def list_registers(regs):
    if not regs:
        print("No registers loaded.")
        return
    print("Idx  Addr  Value  Name")
    for idx, reg in enumerate(regs):
        print(f"[{idx:02d}] 0x{reg['addr']:02X} 0x{reg['value']:03X} {reg['name']}")


def write_register(bus: SMBus, addr: int, value: int):
    high = ((addr & 0x7F) << 1) | ((value >> 8) & 0x1)
    low = value & 0xFF
    bus.write_i2c_block_data(WM8960_ADDR, high, [low])


def write_reg(bus: SMBus, reg: int, value: int):
    # reg: 0–0x34, value: 0–0x1FF
    high = ((reg & 0x7F) << 1) | ((value >> 8) & 0x1)
    low = value & 0xFF
    bus.write_i2c_block_data(WM8960_ADDR, high, [low])


def read_reg(bus: SMBus, reg: int) -> int:
    # Some WM8960 variants don’t support reads; expect IOError if so.
    addr_byte = (reg & 0x7F) << 1
    bus.write_byte(WM8960_ADDR, addr_byte)  # set register pointer
    data = bus.read_i2c_block_data(WM8960_ADDR, 0, 2)
    return ((data[0] & 0x1) << 8) | data[1]


def main():
    bus_num = choose_bus()
    # Show a quick scan like `i2cdetect -y <bus>`.
    scan_bus(bus_num)

    addr_input = input("Enter WM8960 I2C address (default 0x1a, alt 0x1b): ").strip()
    if addr_input:
        global WM8960_ADDR
        try:
            WM8960_ADDR = int(addr_input, 0)
        except ValueError:
            print("Invalid address; using default 0x1a.")
            WM8960_ADDR = 0x1A

    # Final probe before writing.
    tag = probe_bus_for_wm8960(bus_num)
    if "device responded" not in tag:
        cont = input(
            f"No WM8960 response on /dev/i2c-{bus_num}. Continue anyway? [y/N]: "
        ).strip().lower()
        if cont not in ("y", "yes"):
            sys.exit(1)

    reg_file = input("Path to register file (txt, optional): ").strip()
    registers = parse_register_file(reg_file) if reg_file else []
    if registers:
        print(f"Loaded {len(registers)} registers from {reg_file}")
    else:
        print("No register file loaded; you can still write manually.")

    with SMBus(bus_num) as bus:
        print(HELP_TEXT)
        while True:
            cmd = input("i2c> ").strip()
            if not cmd:
                continue
            parts = cmd.split()
            action = parts[0].lower()

            if action in ("quit", "exit"):
                break
            if action == "help":
                print(HELP_TEXT)
            elif action == "list":
                list_registers(registers)
            elif action == "set" and len(parts) == 3:
                try:
                    idx = int(parts[1])
                    val = int(parts[2], 0)
                except ValueError:
                    print("Usage: set <idx> <value>")
                    continue
                if idx < 0 or idx >= len(registers):
                    print("Index out of range.")
                    continue
                registers[idx]["value"] = val & 0x1FF
                print(f"Set {registers[idx]['name']} to 0x{val:03X}")
            elif action == "write" and len(parts) == 2:
                try:
                    idx = int(parts[1])
                except ValueError:
                    print("Usage: write <idx>")
                    continue
                if idx < 0 or idx >= len(registers):
                    print("Index out of range.")
                    continue
                reg = registers[idx]
                try:
                    write_register(bus, reg["addr"], reg["value"])
                    print(f"Wrote 0x{reg['value']:03X} to 0x{reg['addr']:02X} ({reg['name']})")
                except OSError as e:
                    print(f"Write failed: {e}")
            elif action == "writeall":
                if not registers:
                    print("No registers loaded.")
                    continue
                for reg in registers:
                    try:
                        write_register(bus, reg["addr"], reg["value"])
                        print(f"Wrote 0x{reg['value']:03X} to 0x{reg['addr']:02X} ({reg['name']})")
                    except OSError as e:
                        print(f"Write failed for 0x{reg['addr']:02X}: {e}")
                        break
            elif action in ("writeaddr", "wa") and len(parts) == 3:
                try:
                    addr = int(parts[1], 0)
                    val = int(parts[2], 0) & 0x1FF
                except ValueError:
                    print("Usage: writeaddr <addr> <val>")
                    continue
                try:
                    write_register(bus, addr, val)
                    print(f"Wrote 0x{val:03X} to 0x{addr:02X}")
                except OSError as e:
                    print(f"Write failed: {e}")
            elif action in ("setaddr", "sa") and len(parts) == 3:
                try:
                    addr = int(parts[1], 0)
                    val = int(parts[2], 0) & 0x1FF
                except ValueError:
                    print("Usage: setaddr <addr> <val>")
                    continue
                # Update first matching register in list, if present.
                updated = False
                for reg in registers:
                    if reg["addr"] == addr:
                        reg["value"] = val
                        print(f"Set {reg['name']} (0x{addr:02X}) to 0x{val:03X}")
                        updated = True
                        break
                if not updated:
                    print("Address not in loaded register list.")
            elif action == "macro" and len(parts) >= 2:
                name = parts[1]
                if name not in MACROS:
                    print(f"Unknown macro '{name}'. Available: {', '.join(MACROS.keys())}")
                    continue
                seq = MACROS[name]
                print(f"Running macro '{name}' ({len(seq)} writes)")
                for addr, val, desc in seq:
                    try:
                        write_register(bus, addr, val)
                        print(f"  0x{addr:02X} <- 0x{val:03X} ({desc})")
                    except OSError as e:
                        print(f"  Write failed at 0x{addr:02X}: {e}")
                        break
            else:
                print("Unknown command. Type 'help' for options.")


if __name__ == "__main__":
    main()
