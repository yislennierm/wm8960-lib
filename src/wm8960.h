

// ADD HEADER INFORMATION LATER

/** 
 * @name WM8660_R0_LEFT_IN_VOL (0x00)
 * @brief Left input PGA volume control. Default 0x017 = 0 dB, unmuted.
 * Fields:
 * BIT 8        IPVU        (volume update) - DEF. N/A
 * BIT 7        LINMUTE     (L input mute) - DEF. 0 MUTE
 * BIT 6        LIZC        (zero-cross) - DEF. 0 - Immediately
 * BIT [5:0]    LINVOL      (L input volume lvl.) - DEF. 010111 (Min 30db - Min -17.25dB - 0.75dB steps)
*/

#define WM8960_R0_ADDR            0x00u
#define WM8960_R0_IPVU            (1u << 8)  /* Input PGA volume update */
#define WM8960_R0_LINMUTE         (1u << 7)  /* Input PGA analogue mute */
#define WM8960_R0_LIZC            (1u << 6)  /* Input PGA zero-cross enable */
#define WM8960_R0_LINVOL_MASK     0x3Fu      /* bits 5:0 volume code */
#define WM8960_R0_LINVOL_SHIFT    0
#define WM8960_R0_LINVOL_0DB      0x17u
#define WM8960_R0_LINVOL_MAX_30DB 0x3Fu
/** @} WM8960_R0_LEFT_IN_VOL */




/**
 * \{
 * @name WM8960_REG_LEFT_IN_VOL (0x00) and WM8960_REG_RIGHT_IN_VOL (0x01)
 * Bit definitions for the WM8960_REG_LEFT_IN_VOL
 * and WM8960_REG_RIGHT_IN_VOL register
 */
#define WM8960_LEFT_RIGHT_IN_VOL_IPVU           0x100u /**< Input PGA Volume Update */
#define WM8960_LEFT_RIGHT_IN_VOL_INMUTE         0x080u /**< Input PGA Analogue Mute */
#define WM8960_LEFT_RIGHT_IN_VOL_IZC_ZC         0x040u /**< Input PGA Zero Cross Detector */
#define WM8960_LEFT_RIGHT_IN_VOL_INVOL_0dB      0x017u /**< Input PGA Volume 0dB */
#define WM8960_LEFT_RIGHT_IN_VOL_INVOL_30dB     0x03Fu /**< Input PGA Volume 30dB */
/** \} WM8960_REG_LEFT_IN_VOL and WM8960_REG_RIGHT_IN_VOL */