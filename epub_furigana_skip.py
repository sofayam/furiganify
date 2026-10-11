#!/usr/bin/env python3
"""
epub_furigana.py - add furigana (ruby) to every kanji in a Japanese EPUB.

Usage:
    python epub_furigana.py input.epub [output.epub] [--skip LEVEL]
                            [--known-kanji CHARS]

    --skip LEVEL   Leave kanji you probably already know un-annotated, so only
                   the harder ones get furigana. LEVEL is one of:
                     n5 n4 n3 n2   skip kanji up to that JLPT level
                                   (n4 = skip N5+N4, a common learner choice)
                     g1 ... g6     skip kanji up to that Japanese school grade
                   Default: no skipping, every kanji gets furigana.
    --known-kanji  Extra kanji to treat as known, e.g. --known-kanji 鬼魔

If output is omitted, "<input>_furigana.epub" is written next to the input.

Setup (one time, needs internet only for this step):
    pip install lxml fugashi unidic-lite

Behaviour:
  * Kanji that already have <ruby> furigana are left exactly as they are.
  * Every other kanji (or, with --skip, every kanji above your level) gets <ruby><rb>漢字</rb><rt>かんじ</rt></ruby>.
  * Okurigana stays outside the ruby: 食べる -> <ruby>食 (た)</ruby>べる
  * With --skip, a kanji word is annotated if ANY kanji in it is above your
    level (so 学校 is skipped at g2, but 学園 is annotated as a whole word).
  * Only the book text is changed (XHTML/HTML files). Images, CSS, the
    table of contents, and metadata are copied through untouched.
  * The EPUB must be DRM-free.

Readings come from the UniDic dictionary via fugashi. They are right most of
the time but not always (context-dependent readings, names, wordplay).
Add your own fixes to READING_OVERRIDES below.
"""
import argparse
import os
import re
import sys
import zipfile

from lxml import etree
from fugashi import Tagger

# surface form -> (analyzer reading, replacement). Edit freely.
# Keys are matched against the whole token, e.g. "日本".
READING_OVERRIDES = {
    "日本": "にほん",
}

XHTML_NS = "http://www.w3.org/1999/xhtml"
KANJI = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3005\u30f6"  # incl. 々 and ヶ
KANJI_RE = re.compile("[%s]" % KANJI)
RUNS_RE = re.compile("[%s]+|[^%s]+" % (KANJI, KANJI))
SKIP_TAGS = {"ruby", "rt", "rb", "rp", "head", "title", "script", "style"}

# Kanji lists (JLPT: community 'new' N5-N1 lists; grades: Japanese school grades 1-6).
# Stored as increments; they are combined cumulatively below.
_JLPT_INC = {
    5: '一二九七人入八十三上下大女山川土千子小中五六円天日月木水火出右四左本白万今午友父北半外母休先名年気百男見車毎行西何来学金雨国東長前南後食校時高間話電聞語読生書',
    4: '力口工夕手文犬正田目立元公切少心方牛止兄冬古台広用世主代写去字早町花赤足不仕会同多考肉自色体作図売弟社言走近空青音地安有死京夜妹姉店明歩画知室思海茶以夏家紙通強教理週魚鳥黒住医究者研場朝答買道楽事使始服物屋度待持界発送重起院終習転運開集飲業漢歌親病別注洋特意味勉旅員動悪族着野風新問銀題館駅料映私帰春昼秋計建英飯曜品急真堂試借験質貸',
    3: '才王石内太引市他号平打申礼耳交光回当米声形草化両全向曲次直活点科首欠由民付失必未末記組船雪支助君対局役投決馬番絵数所具受和定実泳苦表部乗客相美負談要勝速配酒進落葉路鳴横調頭顔最争伝共好成老位初利努労命放昔育指神追戦良便働庭息流消都商深球陽寒悲期歯港登亡合予反返宿想感暗様福殺然熱選願情疑皆例参完念折望束残求約性格能術晴列式信単変夫昨法晩猫園遠係取守幸箱面喜治笑辞関政留険危存原薬側席敗果因常識非官察愛警覚説告種達類報等座忘洗許静煙加容易財若忙徒得続連困機飛害余難確在夢産倒妻議犯罪論経済判制務資権件断任責増解際認過寝置費示観値吸状収職規割演師備優宅現呼違差供限与渡景抜候構捕慣満掛居突招段腹痛退迷訪怒眠靴途給冷処婦程精絶杯積寄娘怖恐婚遊貧適押更浮越背盗除幾散似富探迎祖雑賛込欲閉窓否暮誤降勤刻遅破互彼恥払舞頼戻抱緒逃御吹到髪疲歳偶偉頂',
    2: '了丸玉久戸毛央氷皮皿竹糸虫村貝池羽角谷麦林州血星札辺弱黄森雲県軽農鉄算線仲低岸波拾秒競令根倍島祭章童階植温湯短泉橋緑練億課賞輪像卒協周囲固季希材芸技骨寺岩区坂勇毒浅軍仏築門荷府浴専細鼻兵塩栄干底署恋訓祈焼胸脳枚禁喫減順布詞歴冊宇団暴混乱改絡比被震械個圧厚防史委査総設省税各勢営領副域停革律準則導乳城担額輸燃祝届肩腕腰触層型庁管象量境武述販含況補効豊巻捜替造印復筆貯刺郵針菓河汗再接占胃悩昇濃極逆巨庫児凍幼清録券移並乾欧臣略航板詰照快版預延翌符編普掃泥棒孫帯粉菜貨陸均採永液績複党卵捨汚机簡誌宝尊敬灰砂著蒸蔵装裏諸臓純紅拝劇承損枝測講紹介湖銅油旧姓貿将伸幅甘換療般依漁募患湾爆跡香兆齢刊傾奥贈超雇片群埋駐柱鋭殿薄伺炭包衣鉱双床掘泊荒袋珍籍刷封筒柔沈辛匹叫涙缶粒塔肌舟曇磨湿硬鈍涼零綿帽憎滴畳畜溶踊賢灯咲塗召挟枯沸濯燥瓶耕肯脂膚軒軟郊隅隻',
}
_GRADE_INC = {
    1: '一二九七人入八力十三上下口大女山川土千夕子小中五六円天手文日月木水火犬王出右四左本正玉田白目石立休先名字年早気百竹糸耳虫村男町花見貝赤足車学林空金雨青草音校森生',
    2: '工刀丸才万今元公内分切午友太少引心戸方牛父毛止兄冬北半古台外市広母用矢交会光同回多当毎池米羽考肉自色行西何体作図声売弟形来社角言谷走近里麦地京国夜妹姉店明東歩画直知長前南室後思星活海点科茶食首夏家弱時紙記通高強教理組船週雪魚鳥黄黒馬場朝番答絵買道間雲数楽話電歌算聞語読鳴線親頭顔野合風新寺岩帰春昼晴秋計園曜書遠門原細弓汽',
    3: '丁世主他代写去号央平打氷申皮皿礼仕化両全向安州曲有次死羊血由住助医君対局役投決究身者研所事使具受和始定実服泳物苦表部乗客屋度待持界発相県美負送重談勝起速配酒院終習転進落葉軽運開集飲業漢路農鉄横調病命岸放昔波注育拾指洋神秒級追意味勉庭息旅根流消倍員島祭章第都動商悪族深球童陽階寒悲暑期植歯温港湯登着短予反返問宿想感整暗様橋福緑練詩銀題館駅列区坂式係取品守幸急真箱荷面薬鼻等笛委宮筆庫板遊豆湖油昭柱炭畑帳',
    4: '不欠氏札民辺付以失必未末要最争仲伝共好成老位低初別利努労戦競良功特便働令億器士料標殺然熱課賞輪選鏡願養例卒協参周囲固季完希念折望材束松残求的約芸信勇単司変夫建昨毒法泣浅紀英軍飯典喜府治浴笑辞関側兵堂塩席敗果栄梅無結官察底愛覚説訓試告種達類借焼験静加節順歴徒得改続連機飛害械産議史挙省各案置費副観停祝型差管象量票景候満印貯胃極健康給児冷博清録隊積臣航街旗照倉孫巣帯径救散粉脈菜貨陸漁兆唱包衣牧刷芽灯郡腸',
    5: '久支仮像情謝基性技格能術仏築保弁政留証険因常識非報可許句禁減容布易財舌団暴混比災率余確個圧在夢厚妻犯罪防経敵判制務査総設資件素断評任検条責増税解際義過価勢営示統領応提状態賀職規護演師準則備導幹張現額製輸燃境武質述限構効属慣豊肥居造授復往故河再接独招退織貸迷逆潔修券婦益移程精絶略寄快版貧適預編似均墓富徳序志恩採桜永液眼祖績興衛複雑賛酸銭飼承損枝測破舎講銅旧貿刊群鉱俵綿耕',
    6: '泉亡映疑私骨晩危存専干署警座忘洗胸脳枚若詞冊宇宙乱善困難穴論済権派批認誕策値吸域姿収革割裁律看優宅乳呼城俳担届層庁視供展株補模巻創障従我激討郵針段腹痛就訪幼処並憲衆閣宗系延翌覧背除棒探傷党卵厳捨密欲暖机秘訳染簡閉誌窓否筋垂宝宣尊忠拡操敬暮灰熟異皇盛砂糖納肺著蒸蔵装裏諸賃誤臓貴降縮純縦聖磁紅射幕拝推揮沿源劇勤刻己将盟遺臨奏片鋼孝樹仁至誠郷朗潮寸尺班陛后奮頂穀絹蚕',
}


def build_known(skip, extra):
    """Return the set of kanji that should NOT get furigana."""
    known = set(extra or "")
    if skip:
        kind, n = skip[0].lower(), int(skip[1:])
        table = _JLPT_INC if kind == "n" else _GRADE_INC
        # JLPT: 5 is easiest, so n4 = {5, 4}; grades: g3 = {1, 2, 3}
        wanted = [k for k in table if (k >= n if kind == "n" else k <= n)]
        for k in wanted:
            known.update(table[k])
    return known


KNOWN = set()  # filled in by main()
ITERATION_MARKS = "\u3005\u30f6"  # 々 ヶ never decide on their own

tagger = Tagger()
unreadable = {}


def kata2hira(s):
    return "".join(
        chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in s
    )


def align(surface, reading):
    """Split a token into (text, reading-or-None) pieces so okurigana stays plain."""
    runs = RUNS_RE.findall(surface)
    if len(runs) == 1:
        return [(surface, reading)]
    pattern = ""
    for run in runs:
        if KANJI_RE.match(run[0]):
            pattern += "(.+?)"
        else:
            pattern += re.escape(kata2hira(run))
    m = re.fullmatch(pattern, reading)
    if not m:  # alignment failed: put the whole reading over the whole token
        return [(surface, reading)]
    out, group = [], 1
    for run in runs:
        if KANJI_RE.match(run[0]):
            out.append((run, m.group(group)))
            group += 1
        else:
            out.append((run, None))
    return out


def needs_furigana(kanji_run):
    """True if any kanji in the run is outside the user's known set."""
    return any(
        c not in KNOWN and c not in ITERATION_MARKS
        for c in kanji_run
        if KANJI_RE.match(c)
    )


def segments(text):
    """Return [(text, reading-or-None), ...] for a plain string."""
    segs = []
    for tok in tagger(text):
        surface = tok.surface
        if not KANJI_RE.search(surface):
            segs.append((surface, None))
            continue
        kana = getattr(tok.feature, "kana", None)
        if surface in READING_OVERRIDES:
            reading = READING_OVERRIDES[surface]
        elif kana and kana != "*":
            reading = kata2hira(kana)
        else:
            unreadable[surface] = unreadable.get(surface, 0) + 1
            segs.append((surface, None))
            continue
        for piece, rd in align(surface, reading):
            if rd is not None and not needs_furigana(piece):
                rd = None
            segs.append((piece, rd))
    merged = []
    for t, r in segs:
        if r is None and merged and merged[-1][1] is None:
            merged[-1] = (merged[-1][0] + t, None)
        else:
            merged.append((t, r))
    return merged


def make_ruby(ns, text, reading):
    ruby = etree.Element("{%s}ruby" % ns if ns else "ruby")
    rb = etree.SubElement(ruby, "{%s}rb" % ns if ns else "rb")
    rb.text = text
    rt = etree.SubElement(ruby, "{%s}rt" % ns if ns else "rt")
    rt.text = reading
    return ruby


def localname(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else None


def process(el, ns):
    name = localname(el)
    if name is None or name in SKIP_TAGS:  # comments, PIs, ruby, head...
        return

    inserted = []
    if el.text and KANJI_RE.search(el.text):
        segs = segments(el.text)
        el.text = None
        for t, r in segs:
            if r is None:
                if inserted:
                    inserted[-1].tail = (inserted[-1].tail or "") + t
                else:
                    el.text = (el.text or "") + t
            else:
                inserted.append(make_ruby(ns, t, r))
        for i, node in enumerate(inserted):
            el.insert(i, node)
    new_ids = {id(n) for n in inserted}

    for child in list(el):
        if id(child) in new_ids:
            continue
        process(child, ns)
        if child.tail and KANJI_RE.search(child.tail):
            segs = segments(child.tail)
            child.tail = None
            idx = el.index(child)
            prev = child
            for t, r in segs:
                if r is None:
                    prev.tail = (prev.tail or "") + t
                else:
                    node = make_ruby(ns, t, r)
                    idx += 1
                    el.insert(idx, node)
                    prev = node


def convert_document(data):
    parser = etree.XMLParser(resolve_entities=False, remove_blank_text=False)
    tree = etree.fromstring(data, parser).getroottree()
    root = tree.getroot()
    ns = etree.QName(root).namespace or XHTML_NS
    process(root, ns)
    doctype = tree.docinfo.doctype or None
    return etree.tostring(
        tree, xml_declaration=True, encoding="UTF-8", doctype=doctype
    )


def main():
    ap = argparse.ArgumentParser(
        description="Add furigana to every kanji in a Japanese EPUB."
    )
    ap.add_argument("input")
    ap.add_argument("output", nargs="?")
    ap.add_argument(
        "--skip",
        metavar="LEVEL",
        type=str.lower,
        choices=["n5", "n4", "n3", "n2"] + ["g%d" % i for i in range(1, 7)],
        help="don't annotate kanji up to this JLPT level (n5-n2) or school "
        "grade (g1-g6); default: annotate everything",
    )
    ap.add_argument(
        "--known-kanji",
        default="",
        help="extra kanji to leave un-annotated, e.g. --known-kanji 鬼魔",
    )
    args = ap.parse_args()

    global KNOWN
    KNOWN = build_known(args.skip, args.known_kanji)
    if args.skip or args.known_kanji:
        print("Skipping %d known kanji; annotating the rest." % len(KNOWN))

    src = args.input
    dst = args.output or os.path.splitext(src)[0] + "_furigana.epub"
    if os.path.abspath(src) == os.path.abspath(dst):
        sys.exit("Output must be a different file from the input.")

    with zipfile.ZipFile(src) as zin:
        names = zin.namelist()
        if any(n.endswith("META-INF/encryption.xml") for n in names):
            print("Warning: encryption.xml found; font obfuscation is fine, "
                  "but DRM-protected books cannot be processed.")
        # mimetype must come first and be stored uncompressed
        ordered = sorted(names, key=lambda n: 0 if n == "mimetype" else 1)
        with zipfile.ZipFile(dst, "w") as zout:
            for n in ordered:
                data = zin.read(n)
                if n == "mimetype":
                    zout.writestr(n, data, compress_type=zipfile.ZIP_STORED)
                    continue
                if n.lower().endswith((".xhtml", ".html", ".htm")):
                    try:
                        data = convert_document(data)
                        print("converted", n)
                    except etree.XMLSyntaxError as e:
                        print("skipped (not well-formed XML): %s (%s)" % (n, e))
                zout.writestr(n, data, compress_type=zipfile.ZIP_DEFLATED)

    print("\nWrote", dst)
    if unreadable:
        print("No reading found for:", unreadable)


if __name__ == "__main__":
    main()
