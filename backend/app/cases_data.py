"""病例库元数据 —— 单点真相（Single Source of Truth）。

【为什么独立成模块】
Spec §9 要求病例的「中文名 / 简介 / 症状要点 / 防治要点 / 例图」不得硬编码在
路由或响应体里。这里集中维护全部 38 个类别（14 种作物），路由与响应体只做透传。

【内容原则（红线：严禁编造）】
- 病害知识取自通用植保常识，面向小农户叙述，不写具体实验数值，
  也不引用来源不明、无法核实的统计数据。
- 防治建议一律以「按登记标签施用」「联系当地植保站复核」收口，
  不给出未经核实的剂量与频次。
- 例图来自仓库内已有的测试素材 `test_assets/`，映射关系由 `image_relpath` 生成。

`class_key` 与训练集目录名、`detector._CN_BY_NAME` 精确对齐（错一个字符就回落英文）；
例图文件名 = class_key 先 `___` 换成 `__`，再去掉逗号、空格换成下划线。
"""

from typing import Dict, Optional, Tuple

HEALTHY = "健康"

# 14 种作物的展示顺序（与 constants.SUPPORTED_CROP_CN 一致）。
CROP_ORDER: Tuple[str, ...] = (
    "tomato", "grape", "corn", "potato", "apple", "peach",
    "strawberry", "pepper_bell", "cherry", "soybean",
    "blueberry", "squash", "raspberry", "orange",
)

# crop_key -> 中文作物名
CROP_CN: Dict[str, str] = {
    "tomato": "番茄", "grape": "葡萄", "corn": "玉米", "potato": "马铃薯",
    "apple": "苹果", "peach": "桃", "strawberry": "草莓", "pepper_bell": "辣椒",
    "cherry": "樱桃", "soybean": "大豆", "blueberry": "蓝莓", "squash": "南瓜",
    "raspberry": "树莓", "orange": "柑橘",
}

_H = "植株长势良好，叶片完整、色泽均匀，未见明显病斑、霉层或畸形，可作为健康对照。"

CASES: Tuple[dict, ...] = (
    {
        "class_key": "Tomato___Bacterial_spot", "crop_key": "tomato", "crop_cn": "番茄", "disease_cn": "细菌性斑点病", "is_healthy": False,
        "summary": "由细菌引起的叶果病害，叶片现深褐色小斑并带黄色晕圈，果实形成粗糙疮痂状病斑。",
        "symptoms": ("叶片出现深褐色小斑、外围常有黄色晕圈", "病斑密集连片后叶片黄化脱落", "果实表面形成褐色隆起、粗糙的疮痂状斑点"),
        "prevention": ("使用无病种子并做种子消毒，培育无病壮苗", "避免叶面浇水，减少雨水飞溅传播，雨后及时排水", "与非茄科作物轮作，清除病叶病残体"),
    },
    {
        "class_key": "Tomato___Early_blight", "crop_key": "tomato", "crop_cn": "番茄", "disease_cn": "早疫病", "is_healthy": False,
        "summary": "真菌性病害，多由下部老叶先发病，病斑具同心轮纹，是番茄常见的早期叶部病害。",
        "symptoms": ("下部叶片先出现褐色圆形病斑，具明显同心轮纹", "病斑周围常有黄化晕圈，扩大后连片", "茎部与果实也可形成褐色凹陷病斑"),
        "prevention": ("轮作并清除病叶病残体，减少初侵染源", "合理密植、改善通风透光，避免偏施氮肥", "发病初期选用登记杀菌剂，按标签剂量施用并注意轮换"),
    },
    {
        "class_key": "Tomato___Late_blight", "crop_key": "tomato", "crop_cn": "番茄", "disease_cn": "晚疫病", "is_healthy": False,
        "summary": "流行性很强的真菌病害，低温高湿时扩展迅速，叶片现水渍状暗褐病斑并可致成片枯死。",
        "symptoms": ("叶片出现水渍状暗绿至褐色病斑，扩展快", "湿度大时病斑边缘可见白色霉层", "茎与青果也可受害，果面出现褐色硬斑"),
        "prevention": ("优化通风降湿，避免叶面长时间结露", "密切关注天气预报，低温高湿天气前做好预防", "及时拔除并销毁病株，避免田间扩散"),
    },
    {
        "class_key": "Tomato___Leaf_Mold", "crop_key": "tomato", "crop_cn": "番茄", "disease_cn": "叶霉病", "is_healthy": False,
        "summary": "棚室高湿条件下多发的真菌病害，叶背生淡黄至褐色绒状霉层，叶正面出现黄色斑块。",
        "symptoms": ("叶正面出现边界不清的淡黄色斑块", "叶背对应位置长出淡黄至褐色的绒状霉层", "后期叶片卷曲、干枯，由下部向上蔓延"),
        "prevention": ("加强通风、降低棚内湿度，避免夜间叶面结露", "合理密植，及时摘除下部老叶病叶", "发病初期按登记标签选用药剂并注意轮换"),
    },
    {
        "class_key": "Tomato___Septoria_leaf_spot", "crop_key": "tomato", "crop_cn": "番茄", "disease_cn": "斑枯病", "is_healthy": False,
        "summary": "真菌性叶斑病，下部叶片先现圆形褐色小斑，中央灰白并生小黑点，严重时叶片枯黄脱落。",
        "symptoms": ("下部叶片出现圆形褐色小斑，中央渐呈灰白", "病斑上可见细小黑点（分生孢子器）", "病斑密布后叶片枯黄、提早脱落"),
        "prevention": ("清除病叶与病残体，减少越冬菌源", "避免叶面浇水，改滴灌并保持叶面干燥", "轮作并合理密植，发病初期按标签用药"),
    },
    {
        "class_key": "Tomato___Spider_mites Two-spotted_spider_mite", "crop_key": "tomato", "crop_cn": "番茄", "disease_cn": "红蜘蛛（二斑叶螨）", "is_healthy": False,
        "summary": "叶螨危害，刺吸叶片汁液形成灰黄斑驳，叶背可见细小蛛丝与螨体，高温干旱时易暴发。",
        "symptoms": ("叶面出现密集的失绿小点，呈灰黄斑驳", "叶背可见细小蛛丝与微小的螨体", "严重时叶片焦枯、脱落，植株长势衰弱"),
        "prevention": ("及时清除田间杂草与老叶，减少寄主与藏身处", "保护瓢虫等天敌，避免滥用广谱杀虫剂", "点片发生时及时施药，注意轮换以防止抗药性"),
    },
    {
        "class_key": "Tomato___Target_Spot", "crop_key": "tomato", "crop_cn": "番茄", "disease_cn": "靶斑病", "is_healthy": False,
        "summary": "真菌性叶斑病，病斑同心轮纹明显如靶心，严重时连片导致叶片枯死、影响光合。",
        "symptoms": ("叶片出现褐色圆形病斑，具清晰同心轮纹", "病斑边缘常有黄化，扩大后相互连片", "严重时叶片自下而上枯死，果实也可生小斑"),
        "prevention": ("清除病残体、实行轮作，减少菌源", "加强通风降湿，避免密植与叶面长期潮湿", "发病初期选用登记药剂，按标签施用并轮换"),
    },
    {
        "class_key": "Tomato___Tomato_mosaic_virus", "crop_key": "tomato", "crop_cn": "番茄", "disease_cn": "花叶病毒病", "is_healthy": False,
        "summary": "病毒性病害，叶片现黄绿相间的花叶并皱缩变形，植株矮化，果实品质下降。",
        "symptoms": ("新叶出现黄绿相间的花叶斑驳", "叶片皱缩、变窄甚至呈线状畸形", "植株矮化，开花坐果减少，果实品质变差"),
        "prevention": ("使用无毒种子与健壮苗，操作前后注意手与工具消毒", "防控蚜虫等传毒媒介，减少机械传毒", "发现病株及时拔除并带出田间销毁"),
    },
    {
        "class_key": "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "crop_key": "tomato", "crop_cn": "番茄", "disease_cn": "黄化曲叶病毒病", "is_healthy": False,
        "summary": "由烟粉虱传播的病毒性病害，新叶变小并向上卷曲、叶脉间黄化，植株生长受抑、坐果少。",
        "symptoms": ("新叶明显变小、边缘向上卷曲", "叶脉间出现黄化，叶片质地变厚变脆", "植株矮化、节间缩短，开花坐果明显减少"),
        "prevention": ("重点防控烟粉虱等媒介，使用防虫网隔离", "使用无毒苗，及时清除田边杂草寄主", "发现病株尽早拔除，避免成为传播源"),
    },
    {
        "class_key": "Tomato___healthy", "crop_key": "tomato", "crop_cn": "番茄", "disease_cn": HEALTHY, "is_healthy": True,
        "summary": "番茄叶片健康，叶色浓绿、平展无斑点，植株生长正常。",
        "symptoms": ("叶片完整、叶色均匀浓绿，无病斑与霉层", "新梢生长正常，无卷曲、皱缩或畸形", "茎秆与果实无溃疡、无异常色斑"),
        "prevention": ("保持合理密植与通风透光，平衡施用有机肥与磷钾肥", "采用滴灌、避免叶面长期潮湿", "定期田间巡查，及早发现并处理初发病株"),
    },
    {
        "class_key": "Grape___Black_rot", "crop_key": "grape", "crop_cn": "葡萄", "disease_cn": "黑腐病", "is_healthy": False,
        "summary": "真菌性病害，叶现褐色近圆病斑并生小黑点，果实变褐软腐后失水成僵果。",
        "symptoms": ("叶片出现褐色近圆形病斑，边缘深褐、中央灰白", "病斑上散生小黑点，后期叶片易破裂", "果实变褐软腐，失水皱缩形成黑色僵果"),
        "prevention": ("及时清除病叶、病果与僵果，集中销毁", "改善架面通风透光，降低园内湿度", "雨季前后做好预防性用药，按标签剂量施用"),
    },
    {
        "class_key": "Grape___Esca_(Black_Measles)", "crop_key": "grape", "crop_cn": "葡萄", "disease_cn": "枝枯病（黑麻疹病）", "is_healthy": False,
        "summary": "危害多年生木质部的真菌病害，叶片脉间黄化枯焦、枝干内部变褐，树势逐年衰弱。",
        "symptoms": ("叶片脉间出现褪绿黄斑，渐枯焦、仅沿主脉残留绿色", "枝干纵剖可见木质部变褐坏死", "果实表面生黑色小点，严重时整株枯死"),
        "prevention": ("修剪工具消毒，及时保护大剪口与伤口", "及时清除并销毁病枝病株，避免带菌扩繁", "控制结果量、加强树势管理，提高植株抗性"),
    },
    {
        "class_key": "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)", "crop_key": "grape", "crop_cn": "葡萄", "disease_cn": "叶枯病（拟盘多毛孢叶斑病）", "is_healthy": False,
        "summary": "真菌性叶斑病，病斑多角形或不规则褐色，后期连片导致叶片干枯提早脱落。",
        "symptoms": ("叶片出现多角形或不规则褐色病斑", "病斑受叶脉限制，扩大后相互连片", "后期叶片干枯、提早脱落，影响养分积累"),
        "prevention": ("秋后清扫落叶，减少越冬菌源", "改善架面通风降湿，避免密植", "发病初期选用登记药剂，按标签施用"),
    },
    {
        "class_key": "Grape___healthy", "crop_key": "grape", "crop_cn": "葡萄", "disease_cn": HEALTHY, "is_healthy": True,
        "summary": "葡萄叶片健康，叶色正常、叶形完整，无病斑与霉层。",
        "symptoms": ("叶片色泽均匀、叶形完整，无斑点与霉层", "新梢生长整齐，无萎蔫或畸形", "果穗发育正常，无腐烂与僵果"),
        "prevention": ("保持架面通风透光，合理控制负载量", "平衡施肥、适时灌溉，避免园内长期高湿", "定期巡查，发现初发病叶及时摘除"),
    },
    {
        "class_key": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot", "crop_key": "corn", "crop_cn": "玉米", "disease_cn": "灰斑病（尾孢叶斑病）", "is_healthy": False,
        "summary": "真菌性叶斑病，病斑呈长条形灰褐色、受叶脉限制，多从下部叶片向上发展。",
        "symptoms": ("叶片出现长条形灰褐色病斑，边缘受叶脉限制", "病斑可连片，叶面呈灰绿色并逐渐干枯", "多从下部叶片开始，向上部蔓延"),
        "prevention": ("选用抗病品种并实行轮作", "收获后深翻灭茬，清除病残体减少菌源", "合理密植、避免偏施氮肥，改善田间通风"),
    },
    {
        "class_key": "Corn_(maize)___Common_rust_", "crop_key": "corn", "crop_cn": "玉米", "disease_cn": "普通锈病", "is_healthy": False,
        "summary": "真菌性病害，叶片两面散生褐色疱状孢子堆，破裂后散出锈色粉末，严重时叶片提前枯黄。",
        "symptoms": ("叶片两面散生褐色疱状突起（孢子堆）", "孢子堆破裂后散出锈色粉末", "严重时叶片提早枯黄、干枯，影响灌浆"),
        "prevention": ("选用抗病品种，合理布局避免连作", "平衡施肥，避免偏施氮肥导致贪青", "清除病残体，发病初期按登记标签用药"),
    },
    {
        "class_key": "Corn_(maize)___Northern_Leaf_Blight", "crop_key": "corn", "crop_cn": "玉米", "disease_cn": "大斑病", "is_healthy": False,
        "summary": "真菌性叶部病害，病斑呈长梭形灰褐色大斑，湿度大时表面生灰黑色霉层，可致叶片枯死。",
        "symptoms": ("叶片出现长梭形灰褐色大斑，多由下部叶片先发", "湿度大时病斑表面生灰黑色霉层", "病斑连片后叶片枯死，影响籽粒灌浆"),
        "prevention": ("选用抗病品种并轮作倒茬", "深翻灭茬、清除病残体，减少越冬菌源", "注意排水与合理密度，改善通风条件"),
    },
    {
        "class_key": "Corn_(maize)___healthy", "crop_key": "corn", "crop_cn": "玉米", "disease_cn": HEALTHY, "is_healthy": True,
        "summary": "玉米叶片健康，叶色浓绿、叶形舒展，无病斑与霉层。",
        "symptoms": ("叶片宽展、叶色均匀，无长条病斑与锈疱", "植株生长整齐，茎秆坚实", "叶鞘与茎部无腐烂或变色"),
        "prevention": ("合理密植，平衡施肥与灌溉，增强植株抗性", "及时中耕除草，减少病虫滋生环境", "定期巡查，发现早期病斑及时处理"),
    },
    {
        "class_key": "Potato___Early_blight", "crop_key": "potato", "crop_cn": "马铃薯", "disease_cn": "早疫病", "is_healthy": False,
        "summary": "真菌性病害，下部叶片现带同心轮纹的褐色病斑，严重时自下而上枯黄，影响块茎膨大。",
        "symptoms": ("下部叶片出现褐色病斑，具同心轮纹、外有黄晕", "病斑扩大连片，叶片自下而上枯黄", "茎部也可形成褐色凹陷斑"),
        "prevention": ("轮作并清除病残体，选用健康种薯", "平衡施肥、适时灌溉，增强植株抗性", "发病初期选用登记杀菌剂，按标签施用并轮换"),
    },
    {
        "class_key": "Potato___Late_blight", "crop_key": "potato", "crop_cn": "马铃薯", "disease_cn": "晚疫病", "is_healthy": False,
        "summary": "流行性极强的真菌病害，低温高湿时叶片现水渍状暗褐病斑并生白霉，可致成片枯死。",
        "symptoms": ("叶片出现水渍状暗绿至褐色病斑，扩展迅速", "湿度大时病斑边缘生白色霉层", "茎与块茎亦可受害，块茎出现褐色坏死"),
        "prevention": ("选用抗病品种，严格剔除病薯与病害种薯", "关注预报，低温高湿天气前做好预防用药", "发现中心病株及时清除并销毁，防止扩散"),
    },
    {
        "class_key": "Potato___healthy", "crop_key": "potato", "crop_cn": "马铃薯", "disease_cn": HEALTHY, "is_healthy": True,
        "summary": "马铃薯叶片健康，叶色浓绿、叶面平整，无病斑与霉层。",
        "symptoms": ("叶片完整、叶色浓绿，无同心轮纹病斑", "叶背无白色霉层，植株长势均匀", "茎秆健壮，无褐变或腐烂"),
        "prevention": ("选用健康种薯并做好切刀消毒", "合理轮作、平衡施肥，保持田间通风", "注意排水，避免田间长期高湿"),
    },
    {
        "class_key": "Apple___Apple_scab", "crop_key": "apple", "crop_cn": "苹果", "disease_cn": "黑星病", "is_healthy": False,
        "summary": "真菌性病害，叶片现橄榄绿至黑褐色绒状霉斑，后期叶片扭曲早落，果实形成木栓化黑疤。",
        "symptoms": ("叶面出现近圆形橄榄绿至黑褐色霉斑", "潮湿时病斑表面覆绒状霉层，叶片扭曲早落", "果实受害形成木栓化黑疤，影响商品性"),
        "prevention": ("秋冬清扫落叶落果并深埋，减少越冬菌源", "合理修剪改善通风透光，降低叶面湿度", "展叶期注意预防，发病初期按登记标签用药"),
    },
    {
        "class_key": "Apple___Black_rot", "crop_key": "apple", "crop_cn": "苹果", "disease_cn": "黑腐病", "is_healthy": False,
        "summary": "真菌性病害，果实出现同心轮纹状褐腐并皱缩成僵果，枝条形成红褐色凹陷溃疡。",
        "symptoms": ("果实出现褐色水渍状斑并迅速扩大，具同心轮纹", "病果失水皱缩形成黑色僵果，长期挂树", "枝条出现红褐色凹陷溃疡，树皮开裂"),
        "prevention": ("及时清除病果、病枝与僵果并集中销毁", "修剪后保护伤口，减少病菌侵入", "加强肥水管理增强树势，雨季注意排水"),
    },
    {
        "class_key": "Apple___Cedar_apple_rust", "crop_key": "apple", "crop_cn": "苹果", "disease_cn": "雪松苹果锈病", "is_healthy": False,
        "summary": "需转主寄主（桧柏类）的真菌病害，叶片现橙黄色斑点，叶背长出管状锈色孢子器。",
        "symptoms": ("叶片正面出现橙黄色圆形斑点，边缘常具红晕", "叶背对应位置长出管状锈色孢子器", "严重时叶片干枯、提早脱落"),
        "prevention": ("果园周边避免栽植桧柏类转主寄主", "春季展叶期留意天气，雨前做好预防", "及时摘除病叶并清扫落叶，减少再侵染"),
    },
    {
        "class_key": "Apple___healthy", "crop_key": "apple", "crop_cn": "苹果", "disease_cn": HEALTHY, "is_healthy": True,
        "summary": "苹果叶片健康，叶色浓绿、叶面平展，无霉斑、锈斑与溃疡。",
        "symptoms": ("叶片完整、色泽均匀，无绒状霉斑或锈色孢子器", "枝梢生长正常，无溃疡与开裂", "果实表面光洁，无褐腐与黑疤"),
        "prevention": ("保持合理修剪与通风透光", "平衡施用有机肥与磷钾肥，增强树势", "定期巡查，及早发现并处理异常枝叶"),
    },
    {
        "class_key": "Peach___Bacterial_spot", "crop_key": "peach", "crop_cn": "桃", "disease_cn": "细菌性斑点病", "is_healthy": False,
        "summary": "细菌性病害，叶片现紫红色至褐色小斑并易穿孔，果实表面形成褐色凹陷斑点。",
        "symptoms": ("叶片出现紫红色至褐色小斑，病斑脱落后形成穿孔", "病斑密集时叶片黄化、提早脱落", "果实表面出现褐色凹陷斑点，影响外观"),
        "prevention": ("选用抗病品种与无病苗木建园", "清除病枝病叶，减少越冬菌源", "合理修剪通风，减少叶面长时间湿润"),
    },
    {
        "class_key": "Peach___healthy", "crop_key": "peach", "crop_cn": "桃", "disease_cn": HEALTHY, "is_healthy": True,
        "summary": "桃树叶片健康，叶色正常、叶形完整，无穿孔与褐色斑点。",
        "symptoms": ("叶片色泽正常、叶形完整，无穿孔与斑点", "新梢生长健壮，无流胶或溃疡", "果实表面光洁，无凹陷斑点"),
        "prevention": ("合理修剪保持通风透光", "平衡施肥与灌溉，增强树势", "冬季清园，及时清除病残枝"),
    },
    {
        "class_key": "Pepper,_bell___Bacterial_spot", "crop_key": "pepper_bell", "crop_cn": "辣椒", "disease_cn": "细菌性斑点病", "is_healthy": False,
        "summary": "细菌性病害，叶片现水渍状斑点后变褐并带黄晕，果实形成褐色疮痂状病斑。",
        "symptoms": ("叶片出现水渍状小斑，后变褐并带黄色晕圈", "病斑密集时叶片黄化、脱落", "果实出现褐色隆起、疮痂状病斑"),
        "prevention": ("使用无病种子并消毒，培育无病壮苗", "避免叶面浇水，雨后及时排水，减少飞溅传播", "与非茄科作物轮作，清除病残体"),
    },
    {
        "class_key": "Pepper,_bell___healthy", "crop_key": "pepper_bell", "crop_cn": "辣椒", "disease_cn": HEALTHY, "is_healthy": True,
        "summary": "辣椒叶片健康，叶色浓绿、叶面平展，无斑点与霉层。",
        "symptoms": ("叶片完整、叶色浓绿，无水渍状或疮痂状病斑", "植株分枝正常，无萎蔫", "果实表面光洁，无褐斑"),
        "prevention": ("合理密植、通风透光，避免田间高湿", "平衡施肥与灌溉，增强植株抗性", "定期巡查，发现初发病叶及时摘除"),
    },
    {
        "class_key": "Cherry_(including_sour)___Powdery_mildew", "crop_key": "cherry", "crop_cn": "樱桃", "disease_cn": "白粉病", "is_healthy": False,
        "summary": "真菌性病害，叶片正反面出现白色粉状霉层，嫩叶卷曲变形，严重时褪绿褐变早落。",
        "symptoms": ("叶片正反面出现白色粉状霉层", "嫩叶卷曲变形，生长受抑", "严重时叶片褪绿、褐变并提早脱落"),
        "prevention": ("合理密植与修剪，保持通风透光、降低湿度", "及时清除病叶病枝，减少菌源", "发病初期选用登记药剂，按标签交替施用"),
    },
    {
        "class_key": "Cherry_(including_sour)___healthy", "crop_key": "cherry", "crop_cn": "樱桃", "disease_cn": HEALTHY, "is_healthy": True,
        "summary": "樱桃叶片健康，叶色正常、叶面洁净，无白色霉层与卷曲。",
        "symptoms": ("叶片完整、叶色正常，无白色粉状霉层", "叶形舒展，无卷曲与皱缩", "新梢生长健壮，无异常斑点"),
        "prevention": ("保持树冠通风透光，控制园内湿度", "平衡施肥、合理灌溉，增强树势", "定期巡查，及早发现并处理异常叶片"),
    },
    {
        "class_key": "Strawberry___Leaf_scorch", "crop_key": "strawberry", "crop_cn": "草莓", "disease_cn": "叶焦病", "is_healthy": False,
        "summary": "真菌性叶部病害，叶片现紫红色小斑并扩大连片，致叶缘焦枯，严重时整叶褐枯。",
        "symptoms": ("叶片出现紫红色小斑，逐渐扩大", "病斑连片使叶缘焦枯、叶片褐枯", "严重时植株长势衰弱，影响开花坐果"),
        "prevention": ("及时摘除病老叶，保持株间通风", "避免叶面长期潮湿，采用滴灌", "选用无病苗并合理密植，发病初期按标签用药"),
    },
    {
        "class_key": "Strawberry___healthy", "crop_key": "strawberry", "crop_cn": "草莓", "disease_cn": HEALTHY, "is_healthy": True,
        "summary": "草莓叶片健康，叶色鲜绿、叶面平整，无紫红斑点与焦枯。",
        "symptoms": ("叶片完整、叶色鲜绿，无紫红色斑点", "叶缘无焦枯，叶面平整无霉层", "植株生长整齐，无萎蔫"),
        "prevention": ("保持合理密植与通风，避免高湿郁闭", "平衡施肥与滴灌，增强植株抗性", "及时清除老叶与病叶，保持田间卫生"),
    },
    {
        "class_key": "Blueberry___healthy", "crop_key": "blueberry", "crop_cn": "蓝莓", "disease_cn": HEALTHY, "is_healthy": True,
        "summary": "蓝莓叶片健康，叶色浓绿有光泽，无失绿、斑点与霉层。",
        "symptoms": ("叶片浓绿有光泽，无失绿与斑点", "叶形完整，无卷曲或畸形", "新梢生长正常，无枯萎"),
        "prevention": ("保持土壤适宜酸度与有机质含量", "注意排水与覆盖，避免根系长期积水", "定期巡查，及早发现并处理异常"),
    },
    {
        "class_key": "Raspberry___healthy", "crop_key": "raspberry", "crop_cn": "树莓", "disease_cn": HEALTHY, "is_healthy": True,
        "summary": "树莓叶片健康，叶色正常、叶面洁净，无斑点与萎蔫。",
        "symptoms": ("叶片色泽正常、叶形完整，无斑点与霉层", "枝梢生长健壮，无枯萎或溃疡", "果实发育正常，无腐烂"),
        "prevention": ("合理修剪与引缚，保持行间通风透光", "平衡施肥与灌溉，增强植株抗性", "及时清除病残枝，减少病原累积"),
    },
    {
        "class_key": "Soybean___healthy", "crop_key": "soybean", "crop_cn": "大豆", "disease_cn": HEALTHY, "is_healthy": True,
        "summary": "大豆叶片健康，叶色浓绿、叶形完整，无病斑与霉层。",
        "symptoms": ("叶片浓绿、叶形完整，无斑点与霉层", "植株生长整齐，茎秆坚实", "叶背无霉层，无失绿黄化"),
        "prevention": ("合理轮作与密植，改善田间通风", "平衡施肥与灌溉，避免田间长期高湿", "定期巡查，及早发现并处理初发病株"),
    },
    {
        "class_key": "Squash___Powdery_mildew", "crop_key": "squash", "crop_cn": "南瓜", "disease_cn": "白粉病", "is_healthy": False,
        "summary": "真菌性病害，叶片出现白色粉状霉斑并逐渐连片，叶片黄化枯脆，光合能力显著下降。",
        "symptoms": ("叶片出现白色粉状霉斑，逐渐连片", "叶片黄化、变脆，边缘卷曲", "严重时叶片枯死，果实发育受阻"),
        "prevention": ("通风透光、避免过密，控制田间湿度", "合理灌溉，保持叶面干燥", "发病初期选用登记药剂，按标签交替施用"),
    },
    {
        "class_key": "Orange___Haunglongbing_(Citrus_greening)", "crop_key": "orange", "crop_cn": "柑橘", "disease_cn": "黄龙病（青果病）", "is_healthy": False,
        "summary": "由木虱传播的毁灭性病害，叶片斑驳状黄化，果实小而畸形、着色不均，目前无有效药剂可治。",
        "symptoms": ("叶片出现斑驳状黄化，黄绿相间且左右不对称", "新梢黄化，叶片变小、质硬", "果实小而畸形、着色不均，果蒂附近呈青绿色"),
        "prevention": ("使用无病毒苗木，从源头阻断", "重点防控木虱等传播媒介，统一防治", "发现病株及时清除并销毁，切断传播链"),
    },
)

_BY_KEY: Dict[str, dict] = {c["class_key"]: c for c in CASES}


def by_key(class_key: str) -> Optional[dict]:
    """按类别键取病例元信息；不存在返回 None。"""
    return _BY_KEY.get(class_key)


def image_stem(class_key: str) -> str:
    """类别键 -> 例图文件名（不含扩展名）。规则见模块 docstring。"""
    return class_key.replace("___", "__").replace(",", "").replace(" ", "_")


def image_relpath(class_key: str) -> str:
    """类别键 -> 相对 `test_assets/` 的例图路径。"""
    case = _BY_KEY.get(class_key)
    folder = "supported_healthy" if case and case["is_healthy"] else "supported_diseased"
    return f"{folder}/{image_stem(class_key)}.jpg"


def crop_cn(crop_key: str) -> Optional[str]:
    return CROP_CN.get(crop_key)


def crop_cn_by_value(value: str) -> Optional[str]:
    """把筛选参数（crop_key 或中文作物名）统一解析为中文作物名。"""
    if value in CROP_CN:
        return CROP_CN[value]
    if value in CROP_CN.values():
        return value
    return None
