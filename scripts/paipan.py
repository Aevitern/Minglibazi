#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""苍燃九宫盲派 · 排盘器

按《苍燃九宫盲派教学材料》所传法则排四柱、起大运、定司令、判旺衰、列刑冲合害。
仅用标准库，无需安装依赖。

用法：
    python paipan.py 1978-04-12 14:30 --gender 男
    python paipan.py 1978-04-12 14:30 --gender 女 --json
    python paipan.py 1978-04-12 14:30 --gender 男 --shichen standard

输出：四柱（含十神、藏干、星运）、节气定位、人元司令、旺相休囚死、
      旬空、大运、四限、刑冲合害会、桃花。

注意：
1. 输入一律为公历（阳历）日期与北京时间。
2. 默认 --shichen mangpai：盲派「十二属相定时法」，以双数整点（00/02/04…）为时辰
   分界，亥时 22–24、子时 00–02、丑时 02–04……日柱亦于 00:00 换日。此为本书
   P99–P103 所定，与通行「子时 23–01」不同。
3. --shichen standard：通行定时（子时 23–01，晚子时归次日）。
4. 节气用天文算法计算，误差约数分钟；出生时刻距节气 60 分钟内会给出提醒，
   此时月柱须人工复核。
"""

import argparse
import json as _json
import math
import sys
from datetime import datetime, timedelta

# ---------------------------------------------------------------- 基础常量

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

GAN_WUXING = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
              "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
ZHI_WUXING = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
              "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}
GAN_YINYANG = {g: ("阳" if i % 2 == 0 else "阴") for i, g in enumerate(GAN)}
ZHI_YINYANG = {z: ("阳" if i % 2 == 0 else "阴") for i, z in enumerate(ZHI)}

# 地支藏干（本气、中气、余气）
ZHI_CANG = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"], "卯": ["乙"],
    "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"], "午": ["丁", "己"],
    "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"], "酉": ["辛"],
    "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}

# 人元司令分野（依本书 P30 分金口诀：寅月戊七丙七甲十六之属）
FENJIN = {
    "寅": [("戊", 7), ("丙", 7), ("甲", 16)],
    "卯": [("甲", 10), ("乙", 20)],
    "辰": [("乙", 9), ("癸", 3), ("戊", 18)],
    "巳": [("戊", 5), ("庚", 9), ("丙", 16)],
    "午": [("丙", 10), ("己", 9), ("丁", 11)],
    "未": [("丁", 9), ("乙", 3), ("己", 18)],
    "申": [("戊", 7), ("壬", 7), ("庚", 16)],
    "酉": [("庚", 10), ("辛", 20)],
    "戌": [("辛", 9), ("丁", 3), ("戊", 18)],
    "亥": [("戊", 7), ("甲", 5), ("壬", 18)],
    "子": [("壬", 10), ("癸", 20)],
    "丑": [("癸", 9), ("辛", 3), ("己", 18)],
}

SHENGXIAO = "鼠牛虎兔龙蛇马羊猴鸡狗猪"

# 十二节（定月柱用），节气黄经
JIE = [("立春", 315), ("惊蛰", 345), ("清明", 15), ("立夏", 45),
       ("芒种", 75), ("小暑", 105), ("立秋", 135), ("白露", 165),
       ("寒露", 195), ("立冬", 225), ("大雪", 255), ("小寒", 285)]
JIE_ZHI = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]

# 天干五合
GAN_HE = {"甲己": "土", "乙庚": "金", "丙辛": "水", "丁壬": "木", "戊癸": "火"}
# 六冲
ZHI_CHONG = [(0, 6), (1, 7), (2, 8), (3, 9), (4, 10), (5, 11)]
# 六合
ZHI_LIUHE = {(0, 1): "土", (2, 11): "木", (3, 10): "火",
             (4, 9): "金", (5, 8): "水", (6, 7): "土"}
# 六害（穿）
ZHI_HAI = [(0, 7), (1, 6), (2, 5), (3, 4), (8, 11), (9, 10)]
# 三刑
ZHI_XING = {
    "寅巳申": "无恩之刑", "丑戌未": "恃势之刑",
    "子卯": "无礼之刑", "辰辰": "自刑", "午午": "自刑",
    "酉酉": "自刑", "亥亥": "自刑",
}
# 六破
ZHI_PO = [(0, 9), (1, 8), (2, 7), (3, 6), (4, 5), (10, 11)]
# 三会
SANHUI = {(2, 3, 4): "东方木", (5, 6, 7): "南方火",
          (8, 9, 10): "西方金", (11, 0, 1): "北方水"}
# 三合
SANHE = {(8, 0, 4): "水局", (11, 3, 7): "木局", (2, 6, 10): "火局",
         (5, 9, 1): "金局"}

# 十神
def shishen(day_gan, other_gan):
    """以日干为准，判断另一天干的十神。"""
    de = GAN.index(day_gan)
    oe = GAN.index(other_gan)
    dw = GAN_WUXING[day_gan]
    ow = GAN_WUXING[other_gan]
    same_polarity = (de % 2) == (oe % 2)
    order = ["木", "火", "土", "金", "水"]
    di, oi = order.index(dw), order.index(ow)
    if dw == ow:
        return "比肩" if same_polarity else "劫财"
    if (di + 1) % 5 == oi:                       # 我生
        return "食神" if same_polarity else "伤官"
    if (di + 2) % 5 == oi:                       # 我克
        return "偏财" if same_polarity else "正财"
    if (oi + 2) % 5 == di:                       # 克我
        return "七杀" if same_polarity else "正官"
    return "偏印" if same_polarity else "正印"    # 生我


# 十二长生
CHANGSHENG = {}
for _g, _start in [("甲", 11), ("乙", 6), ("丙", 2), ("丁", 9), ("戊", 2),
                   ("己", 9), ("庚", 5), ("辛", 0), ("壬", 8), ("癸", 3)]:
    _seq = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
    for _i, _s in enumerate(_seq):
        CHANGSHENG[(_g, (_start + _i) % 12 if _g in "甲丙戊庚壬" else (_start - _i) % 12)] = _s


# ---------------------------------------------------------------- 天文计算

def jd_from_datetime(dt):
    """公历（格里历）→ 儒略日（UT）。"""
    y, m = dt.year, dt.month
    d = dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def delta_t(year):
    """ΔT（秒）近似，2000 年后按缓慢增长。"""
    return 63.0 + 0.32 * (year - 2000)


def sun_apparent_longitude(jd_tt):
    """太阳视黄经（度）。"""
    t = (jd_tt - 2451545.0) / 36525.0
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = 357.52911 + 35999.05029 * t - 0.0001537 * t * t
    mr = math.radians(m)
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(mr)
         + (0.019993 - 0.000101 * t) * math.sin(2 * mr)
         + 0.000289 * math.sin(3 * mr))
    true_long = l0 + c
    omega = math.radians(125.04 - 1934.136 * t)
    app = true_long - 0.00569 - 0.00478 * math.sin(omega)
    return app % 360.0


def solar_term_jd(year, target_deg):
    """求某年太阳视黄经达 target_deg 的时刻（返回 JD，UT）。"""
    # 初值：按黄经粗估日期
    approx_day = {315: 34, 345: 65, 15: 80, 45: 126, 75: 157, 105: 188,
                  135: 220, 165: 250, 195: 281, 225: 312, 255: 343, 285: 6}[target_deg]
    y = year
    if target_deg == 285:            # 小寒在 1 月，属上一年序
        y = year
    base = datetime(y, 1, 1) + timedelta(days=approx_day - 1)
    jd = jd_from_datetime(base)
    for _ in range(12):
        lon = sun_apparent_longitude(jd + delta_t(base.year) / 86400.0)
        diff = (target_deg - lon + 180) % 360 - 180
        jd += diff / 0.9856473
        if abs(diff) < 1e-7:
            break
    return jd


def jd_to_bjt(jd):
    """JD(UT) → 北京时间 datetime。"""
    jd += 8 / 24.0
    z = math.floor(jd + 0.5)
    f = jd + 0.5 - z
    alpha = math.floor((z - 1867216.25) / 36524.25)
    a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)
    day = b - d - math.floor(30.6001 * e) + f
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    day_int = int(math.floor(day))
    frac = (day - day_int) * 24
    hh = int(frac)
    mm = int(round((frac - hh) * 60))
    if mm == 60:
        mm = 0
        hh += 1
    if hh == 24:
        hh = 0
        day_int += 1
    return datetime(year, month, day_int, hh, mm)


def all_jie(year):
    """该年十二节的北京时间（含上年小寒至本年大雪）。"""
    out = []
    for name, deg in JIE:
        jd = solar_term_jd(year, deg)
        dt = jd_to_bjt(jd)
        out.append((name, deg, dt))
    out.sort(key=lambda x: x[2])
    return out


# ---------------------------------------------------------------- 四柱

def four_pillars(dt, shichen_mode="mangpai"):
    # --- 年柱：以立春为界
    lichun = [x for x in all_jie(dt.year) if x[0] == "立春"][0][2]
    if dt >= lichun:
        year_for_pillar = dt.year
    else:
        year_for_pillar = dt.year - 1
        lichun = [x for x in all_jie(dt.year - 1) if x[0] == "立春"][0][2]
    y_idx = (year_for_pillar - 1984) % 60
    year_gan, year_zhi = GAN[y_idx % 10], ZHI[y_idx % 12]

    # --- 月柱：以节为界（取出生前最近的节）
    jie_list = []
    for y in (dt.year - 1, dt.year, dt.year + 1):
        jie_list.extend(all_jie(y))
    jie_list.sort(key=lambda x: x[2])
    passed = [j for j in jie_list if j[2] <= dt]
    cur_jie = passed[-1]
    nxt_jie = [j for j in jie_list if j[2] > dt][0]
    jie_name, _, jie_dt = cur_jie
    month_zhi = JIE_ZHI[[j[0] for j in JIE].index(jie_name)]
    # 五虎遁月
    tiger_start = {"甲": "丙", "己": "丙", "乙": "戊", "庚": "戊", "丙": "庚",
                   "辛": "庚", "丁": "壬", "壬": "壬", "戊": "甲", "癸": "甲"}[year_gan]
    offset = JIE_ZHI.index(month_zhi)      # 寅=0
    month_gan = GAN[(GAN.index(tiger_start) + offset) % 10]

    # --- 日柱：以儒略日定，按定时法决定换日点
    day_dt = dt
    if shichen_mode == "standard":
        if dt.hour >= 23:
            day_dt = dt + timedelta(days=1)
    jdn_noon = math.floor(jd_from_datetime(day_dt.replace(hour=12, minute=0)) + 0.5)
    d_idx = (jdn_noon + 49) % 60
    day_gan, day_zhi = GAN[d_idx % 10], ZHI[d_idx % 12]

    # --- 时柱
    h = dt.hour
    if shichen_mode == "mangpai":
        # 双数整点分界：22–24 亥、00–02 子、02–04 丑、04–06 寅、06–08 卯、
        # 08–10 辰、10–12 巳、12–14 午、14–16 未、16–18 申、18–20 酉、20–22 戌
        start = h - (h % 2)
        zhi_i = {22: 11, 0: 0, 2: 1, 4: 2, 6: 3, 8: 4, 10: 5,
                 12: 6, 14: 7, 16: 8, 18: 9, 20: 10}[start]
    else:
        # 通行：23–01 子、01–03 丑 … 21–23 亥
        zhi_i = ((h + 1) // 2) % 12
    hour_zhi = ZHI[zhi_i]
    rat_start = {"甲": "甲", "己": "甲", "乙": "丙", "庚": "丙", "丙": "戊",
                 "辛": "戊", "丁": "庚", "壬": "庚", "戊": "壬", "癸": "壬"}[day_gan]
    hour_gan = GAN[(GAN.index(rat_start) + zhi_i) % 10]

    return {
        "year": (year_gan, year_zhi),
        "month": (month_gan, month_zhi),
        "day": (day_gan, day_zhi),
        "hour": (hour_gan, hour_zhi),
        "meta": {
            "lichun": lichun, "jie": jie_name, "jie_time": jie_dt,
            "next_jie": nxt_jie[0], "next_jie_time": nxt_jie[2],
            "year_for_pillar": year_for_pillar,
        },
    }


# ---------------------------------------------------------------- 分析

def wangxiang(month_zhi):
    """以月令定旺相休囚死，不问日主。"""
    order = ["木", "火", "土", "金", "水"]
    mw = ZHI_WUXING[month_zhi]
    mi = order.index(mw)
    names = ["旺", "相", "休", "囚", "死"]
    # 旺=月令本气；相=月令所生；休=生月令者；囚=克月令者；死=月令所克
    res = {}
    res[mw] = "旺"
    res[order[(mi + 1) % 5]] = "相"
    res[order[(mi - 1) % 5]] = "休"
    res[order[(mi - 2) % 5]] = "囚"       # 克我者
    res[order[(mi + 2) % 5]] = "死"       # 我克者
    return res


def si_ling(month_zhi, days_after_jie):
    """人元司令：出生距节气的天数落在哪一段。"""
    total = 0
    for gan, span in FENJIN[month_zhi]:
        total += span
        if days_after_jie < total:
            return gan
    return FENJIN[month_zhi][-1][0]


def xunkong(gan, zhi):
    """旬空（以日柱起旬）。"""
    gi, zi = GAN.index(gan), ZHI.index(zhi)
    n = 0
    for k in range(60):
        if k % 10 == gi and k % 12 == zi:
            n = k
            break
    xun_start = n - (n % 10)
    kong = [(xun_start + 10) % 12, (xun_start + 11) % 12]
    return ZHI[kong[0]] + ZHI[kong[1]]


def rels(zhis):
    """四支之间的会、合、冲、刑、害、破。"""
    out = []
    idx = [ZHI.index(z) for z in zhis]
    for combo, name in SANHUI.items():
        if all(c in idx for c in combo):
            out.append(("三会", "".join(ZHI[c] for c in combo), name))
    for combo, name in SANHE.items():
        if all(c in idx for c in combo):
            out.append(("三合", "".join(ZHI[c] for c in combo), name))
    for (a, b), name in ZHI_LIUHE.items():
        if a in idx and b in idx:
            out.append(("六合", ZHI[a] + ZHI[b], name))
    for a, b in ZHI_CHONG:
        if a in idx and b in idx:
            out.append(("冲", ZHI[a] + ZHI[b], ""))
    for a, b in ZHI_HAI:
        if a in idx and b in idx:
            out.append(("害", ZHI[a] + ZHI[b], ""))
    for a, b in ZHI_PO:
        if a in idx and b in idx:
            out.append(("破", ZHI[a] + ZHI[b], ""))
    for pat, name in ZHI_XING.items():
        if len(pat) == 3:
            if all(ZHI.index(c) in idx for c in pat):
                out.append(("三刑", pat, name))
        elif len(pat) == 2 and pat[0] != pat[1]:
            if all(ZHI.index(c) in idx for c in pat):
                out.append(("相刑", pat, name))
        else:
            c = ZHI.index(pat[0])
            if idx.count(c) >= 2:
                out.append(("自刑", pat[0] * 2, name))
    # 去重、保序
    seen, uniq = set(), []
    for r in out:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq


def dayun(pillars, dt, gender, meta):
    """起大运：阳男阴女顺，阴男阳女逆；距节气天数 ÷3，余 1 舍、余 2 进。"""
    yg = pillars["year"][0]
    yang = GAN_YINYANG[yg] == "阳"
    forward = (yang and gender == "男") or ((not yang) and gender == "女")
    if forward:
        target = meta["next_jie_time"]
    else:
        target = meta["jie_time"]
    days = abs((target - dt).total_seconds()) / 86400.0
    age = int(days // 3)
    if days % 3 >= 2:
        age += 1
    mg, mz = pillars["month"]
    start = GAN.index(mg), ZHI.index(mz)
    seq = []
    for i in range(1, 11):
        gi = (start[0] + i) % 10 if forward else (start[0] - i) % 10
        zi = (start[1] + i) % 12 if forward else (start[1] - i) % 12
        seq.append((GAN[gi] + ZHI[zi], age + (i - 1) * 10))
    return {"forward": forward, "start_age": age, "list": seq}


def dayun_ganzhi_text(item):
    return "%s（%d岁）" % item


def taohua(year_zhi, day_zhi):
    """桃花（咸池）：三合局之沐浴位。"""
    m = {"申": "酉", "子": "酉", "辰": "酉", "寅": "卯", "午": "卯", "戌": "卯",
         "巳": "午", "酉": "午", "丑": "午", "亥": "子", "卯": "子", "未": "子"}
    return m[year_zhi], m[day_zhi]


def build(dt, gender, shichen_mode):
    p = four_pillars(dt, shichen_mode)
    dg = p["day"][0]
    meta = p["meta"]
    days_after_jie = (dt - meta["jie_time"]).total_seconds() / 86400.0
    month_zhi = p["month"][1]
    siling = si_ling(month_zhi, days_after_jie)
    wx = wangxiang(month_zhi)
    zhis = [p[k][1] for k in ("year", "month", "day", "hour")]
    res = {
        "input": {"datetime": dt.strftime("%Y-%m-%d %H:%M"), "gender": gender,
                  "shichen": shichen_mode},
        "pillars": {k: "".join(p[k]) for k in ("year", "month", "day", "hour")},
        "gan_shishen": {k: shishen(dg, p[k][0]) for k in ("year", "month", "day", "hour")},
        "canggan": {k: [{"gan": g, "shishen": shishen(dg, g), "changcheng": CHANGSHENG.get((dg, ZHI.index(p[k][1])), "")}
                        for g in ZHI_CANG[p[k][1]]] for k in ("year", "month", "day", "hour")},
        "siling": siling,
        "wangxiang": {k: v for k, v in wx.items()},
        "xunkong": xunkong(p["day"][0], p["day"][1]),
        "relations": rels(zhis),
        "taohua": {"by_year": taohua(p["year"][1], p["day"][1])[0],
                   "by_day": taohua(p["year"][1], p["day"][1])[1]},
        "jie": {"current": meta["jie"], "at": meta["jie_time"].strftime("%Y-%m-%d %H:%M"),
                "next": meta["next_jie"], "next_at": meta["next_jie_time"].strftime("%Y-%m-%d %H:%M"),
                "days_in": round(days_after_jie, 2)},
        "lichun": meta["lichun"].strftime("%Y-%m-%d %H:%M"),
        "bindary": (min(abs((meta["jie_time"] - dt).total_seconds()),
                        abs((meta["next_jie_time"] - dt).total_seconds())) / 3600.0),
    }
    res["dayun"] = dayun(p, dt, gender, meta)
    res["four_limits"] = [("年柱", 0, 18), ("月柱", 18, 36), ("日柱", 36, 54), ("时柱", 54, 72)]
    return res


def render(r):
    L = []
    inp = r["input"]
    L.append("【输入】%s  性别：%s   定时法：%s" % (inp["datetime"], inp["gender"],
                                              "盲派十二属相定时（双数整点分界）" if inp["shichen"] == "mangpai" else "通行定时（子时23–01）"))
    L.append("")
    heads = [("年柱", "year"), ("月柱", "month"), ("日柱", "day"), ("时柱", "hour")]
    L.append("四柱：  " + "  ".join("%s %s" % (n, r["pillars"][k]) for n, k in heads))
    L.append("十神：  " + "  ".join("%s %s" % (n, r["gan_shishen"][k]) for n, k in heads))
    for n, k in heads:
        cc = "／".join("%s%s(%s)" % (c["gan"], c["shishen"], c["changcheng"]) for c in r["canggan"][k])
        L.append("  %s支藏：%s" % (n[0], cc))
    L.append("")
    j = r["jie"]
    L.append("【节令】前节 %s %s（已过 %.2f 天） | 后节 %s %s" % (j["current"], j["at"], j["days_in"], j["next"], j["next_at"]))
    L.append("【立春】%s（年柱以此为界）" % r["lichun"])
    L.append("【司令】月令人元司令：%s" % r["siling"])
    L.append("【旺衰】" + "  ".join("%s%s" % (k, v) for k, v in r["wangxiang"].items()) + "（只以月令定，不问日主）")
    L.append("【旬空】日柱旬空：%s" % r["xunkong"])
    L.append("【桃花】年支起：%s ｜ 日支起：%s" % (r["taohua"]["by_year"], r["taohua"]["by_day"]))
    if r["relations"]:
        L.append("【刑冲合害】" + "；".join("%s %s %s" % (a, b, c) for a, b, c in r["relations"]))
    else:
        L.append("【刑冲合害】四支无会合冲刑害破")
    L.append("")
    d = r["dayun"]
    L.append("【大运】%s，%d 岁起运" % ("顺行" if d["forward"] else "逆行", d["start_age"]))
    L.append("  " + "  ".join("%s(%d)" % (g, a) for g, a in d["list"][:8]))
    L.append("")
    L.append("【四限】" + "  ".join("%s %d–%d" % f for f in r["four_limits"]))
    if r["bindary"] < 1.0:
        L.append("")
        L.append("⚠ 出生时刻距节气不足 1 小时，月柱须人工复核（节气算法误差约数分钟）。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="苍燃九宫盲派排盘器")
    ap.add_argument("date", help="公历日期 YYYY-MM-DD")
    ap.add_argument("time", nargs="?", default="12:00", help="出生时间 HH:MM（北京时间）")
    ap.add_argument("--gender", "-g", default="男", choices=["男", "女"], help="性别")
    ap.add_argument("--shichen", default="mangpai", choices=["mangpai", "standard"],
                    help="定时法：mangpai=盲派双数整点分界（默认）；standard=通行子时23–01")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    try:
        dt = datetime.strptime("%s %s" % (args.date, args.time), "%Y-%m-%d %H:%M")
    except ValueError:
        sys.exit("日期或时间格式有误，应为 YYYY-MM-DD HH:MM")

    r = build(dt, args.gender, args.shichen)
    if args.json:
        print(_json.dumps(r, ensure_ascii=False, indent=2, default=str))
    else:
        print(render(r))


if __name__ == "__main__":
    main()
