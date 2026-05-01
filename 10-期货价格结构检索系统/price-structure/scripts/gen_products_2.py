#!/usr/bin/env python3
"""第二轮: 剩余stub和低质量品种"""
import json, os

VERSION = "1.3.0"
BASE = "/root/.openclaw/workspace/The_Theory_of_Difference/10-期货价格结构检索系统/price-structure/config/products"

def w(name, data):
    p = os.path.join(BASE, name)
    os.makedirs(p, exist_ok=True)
    for fname, key in [("entities.json","entities"),("chains.json","chains"),
                        ("relations.json","relations"),("polarity.json","polarity"),
                        ("pricing_models.json","models")]:
        obj = {"commodity":data["c"],"symbol":data["s"],"version":VERSION}
        if fname == "polarity.json":
            obj["entries"] = data.get(key,{})
        else:
            obj[key] = data.get(key,[])
        with open(os.path.join(p,fname),"w",encoding="utf-8") as f:
            json.dump(obj,f,ensure_ascii=False,indent=2)
    ne=len(data.get("entities",[])); nc=len(data.get("chains",[]))
    nr=len(data.get("relations",[])); np_=len(data.get("polarity",{}))
    nm=len(data.get("models",[]))
    print(f"  {name}: {ne}e {nc}c {nr}r {np_}p {nm}m")

# ==================== 苹果 ====================
apple = {
    "c":"苹果","s":"AP",
    "entities":[
        {"id":"GEO_300","name":"陕西苹果产区","type":"资源节点","groundBase":"natural","importance":10,
         "description":"中国苹果最大产区，陕西占全国产量约25%，洛川苹果是交割品质标杆","trackingVariables":["种植面积","产量","优果率","天气"]},
        {"id":"GEO_301","name":"山东苹果产区","type":"资源节点","groundBase":"natural","importance":9,
         "description":"中国苹果第二大产区，烟台苹果品质优良","trackingVariables":["产量","优果率","出口量"]},
        {"id":"GEO_302","name":"甘肃/新疆苹果产区","type":"资源节点","groundBase":"natural","importance":7,
         "description":"西北新兴苹果产区，面积持续扩大","trackingVariables":["种植面积","产量"]},
        {"id":"POW_220","name":"郑州商品交易所CZCE","type":"交易所","groundBase":"rule","importance":10,
         "description":"中国苹果期货定价中心，AP合约是全球首个鲜果期货","jurisdiction":"中国",
         "trackingVariables":["AP期价","持仓量","仓单量"]},
        {"id":"VAR_240","name":"CZCE苹果期货价格","type":"大宗商品变量","groundBase":"marginal","importance":10,
         "currentValue":"约8000元/吨","historicalRange":{"min":5000,"max":13000},"recentRange":{"min":6500,"max":11000},"trackingFrequency":"实时"},
        {"id":"VAR_241","name":"苹果现货价格","type":"现货变量","groundBase":"marginal","importance":9,
         "trackingFrequency":"每日","trackingVariables":["栖霞价","洛川价","期现基差"]},
        {"id":"VAR_242","name":"苹果优果率","type":"质量变量","groundBase":"marginal","importance":8,
         "trackingFrequency":"收获季","trackingVariables":["优果率","交割品占比"]},
        {"id":"CUL_220","name":"苹果天气炒作叙事","type":"市场共识","groundBase":"culture","importance":8,
         "description":"苹果花期（4月）霜冻和冰雹是年度最大交易主题","trackingVariables":["花期天气","霜冻预警","冰雹"]},
        {"id":"RUL_220","name":"苹果期货交割标准","type":"交易所规则","groundBase":"rule","importance":8,
         "description":"果径≥80mm，果面着色≥70%，硬度等指标","trackingVariables":["交割标准","仓单注册量","弃仓率"]}
    ],
    "chains":[
        {"id":"C_240","name":"花期霜冻减产推升苹果链","domain":"农产品","groundBase":"natural",
         "triggerEvent":"4月苹果花期遭遇严重霜冻或冰雹",
         "steps":[
             {"seq":1,"from":"花期霜冻","to":"坐果率下降","confidence":"高","lag":"即时","mechanism":"冻花直接影响坐果"},
             {"seq":2,"from":"坐果率下降","to":"产量预估下调","confidence":"高","lag":"1-2周","mechanism":"市场评估减产幅度"},
             {"seq":3,"from":"产量下调","to":"期货价格飙升","confidence":"高","lag":"即时","mechanism":"供给收紧推升价格"},
             {"seq":4,"from":"价格飙升","to":"优果率下降加剧交割紧张","confidence":"中","lag":"收获季","mechanism":"减产年份优果率通常下降"}
         ],"reversalNode":"天气恢复","reversalCondition":"花期天气正常或后期坐果恢复",
         "polarityTensionThreshold":0.75,
         "historicalCases":[{"year":"2018","description":"清明霜冻大减产，苹果从6000涨至12000"},
                            {"year":"2021","description":"局部霜冻，价格短暂冲高后回落"}],
         "reversibility":0.4,"tail_probability":0.2,"minority_protected":False},
        {"id":"C_241","name":"丰产压制苹果价链","domain":"农产品","groundBase":"natural",
         "triggerEvent":"苹果生长季天气良好，丰产预期",
         "steps":[
             {"seq":1,"from":"天气良好","to":"坐果率高","confidence":"高","lag":"季节性","mechanism":"花期天气正常"},
             {"seq":2,"from":"坐果率高","to":"丰产预期","confidence":"高","lag":"月度","mechanism":"产量预估上调"},
             {"seq":3,"from":"丰产预期","to":"期货价格下跌","confidence":"中","lag":"即时","mechanism":"供应增加压制价格"},
             {"seq":4,"from":"价格下跌","to":"入库意愿增强","confidence":"中","lag":"收获季","mechanism":"低价刺激冷库入库"}
         ],"reversalNode":"减产证伪","reversalCondition":"实际产量低于预期",
         "polarityTensionThreshold":0.6,"historicalCases":[],"reversibility":0.6,"tail_probability":0.15,"minority_protected":False}
    ],
    "relations":[
        {"id":"R_580","type":"天气传导","from":"花期天气","to":"苹果产量","strength":0.9,"direction":"直接","groundBase":"natural","lag":"即时",
         "description":"4月花期霜冻/冰雹对产量影响最大","reversalPoint":"花期结束后天气影响减弱"},
        {"id":"R_581","type":"库存传导","from":"冷库苹果库存","to":"苹果价格","strength":0.75,"direction":"反向","groundBase":"marginal","lag":"即时",
         "description":"冷库库存是供需平衡指标","reversalPoint":"库存极低时价格弹性增大"},
        {"id":"R_582","type":"季节性规律","from":"收获入库季","to":"苹果价格","strength":0.7,"direction":"季节性","groundBase":"natural","lag":"季节性",
         "description":"10-11月收获季供应增加压制价格，春节前消费旺季支撑","reversalPoint":"减产年份季节性卖压减弱"},
        {"id":"R_583","type":"替代品传导","from":"其他水果价格","to":"苹果需求","strength":0.5,"direction":"复杂","groundBase":"marginal","lag":"月度",
         "description":"柑橘/梨等水果替代消费","reversalPoint":"苹果作为礼品消费刚性较强"}
    ],
    "polarity":{
        "CZCE苹果期货价格":{"historicalMin":5000,"historicalMax":13000,"recentMin":6500,"recentMax":11000,
                            "reversalSignalPatterns":["花期霜冻","丰产预期","库存变化","消费旺季"]}
    },
    "models":[
        {"id":"M_095","name":"苹果的天气定价模型","domain":"供给定价","groundBase":"natural",
         "formula":"AP_Score = w1*WeatherFactor + w2*InventoryFactor + w3*SeasonalFactor",
         "variables":[
             {"name":"花期天气因子","id":"weather","direction":"不定","weight":0.5},
             {"name":"冷库库存因子","id":"inventory","direction":"反向","weight":0.3},
             {"name":"季节性因子","id":"seasonal","direction":"正向","weight":0.2}
         ],
         "description":"苹果是典型的天气炒作品种，花期天气决定年度供给。冷库库存是中短期供需指标。减产年份优果率下降加剧交割紧张。",
         "dominantPhase":"花期（4月）和收获季（10月）模型最有效",
         "limitation":"苹果期货上市时间短，历史数据有限",
         "trackingVariables":["花期天气","产量预估","冷库库存","优果率"],
         "linkToEntities":["VAR_240","VAR_242"],
         "linkToRelations":["R_580","R_581"],
         "linkToConductionChains":["C_240","C_241"]}
    ]
}

# ==================== 动力煤 ====================
thermal_coal = {
    "c":"动力煤","s":"ZC",
    "entities":[
        {"id":"GEO_310","name":"山西动力煤产区","type":"资源节点","groundBase":"natural","importance":10,
         "description":"中国动力煤最大产区，大同/朔州为核心，产能和运输是核心变量","trackingVariables":["产量","产能","铁路运力"]},
        {"id":"GEO_311","name":"内蒙古动力煤产区","type":"资源节点","groundBase":"natural","importance":9,
         "description":"鄂尔多斯为核心产区，产能释放快","trackingVariables":["产量","产能","环保限产"]},
        {"id":"GEO_312","name":"陕西动力煤产区","type":"资源节点","groundBase":"natural","importance":8,
         "description":"榆林为核心产区，煤质优良","trackingVariables":["产量","产能"]},
        {"id":"GEO_313","name":"秦皇岛港煤炭集散地","type":"物流库存节点","groundBase":"natural","importance":10,
         "description":"中国动力煤定价锚，秦皇岛港价是现货基准","trackingVariables":["港口库存","平仓价","调入量","调出量"]},
        {"id":"POW_230","name":"郑州商品交易所CZCE","type":"交易所","groundBase":"rule","importance":9,
         "description":"动力煤期货定价中心（但2022年后活跃度下降）","jurisdiction":"中国","trackingVariables":["ZC期价","持仓量"]},
        {"id":"POW_231","name":"国家发改委","type":"政策权力机构","groundBase":"order","importance":10,
         "description":"动力煤价格调控核心机构，限价政策直接影响市场","trackingVariables":["限价政策","保供稳价","产能核增"]},
        {"id":"VAR_250","name":"秦皇岛5500大卡动力煤价","type":"大宗商品变量","groundBase":"marginal","importance":10,
         "currentValue":"约850元/吨","historicalRange":{"min":400,"max":2000},"recentRange":{"min":700,"max":1200},"trackingFrequency":"每日"},
        {"id":"VAR_251","name":"电厂煤炭库存","type":"库存变量","groundBase":"marginal","importance":9,
         "trackingFrequency":"每日","trackingVariables":["沿海电厂库存","可用天数"]},
        {"id":"VAR_252","name":"动力煤进口量","type":"贸易变量","groundBase":"marginal","importance":8,
         "trackingFrequency":"月度","trackingVariables":["进口到港量","进口煤价","来源国"]},
        {"id":"CUL_230","name":"保供稳价政策叙事","type":"政策共识","groundBase":"order","importance":9,
         "description":"发改委动力煤限价政策是市场核心约束，限价区间是价格天花板","trackingVariables":["限价政策","产能核增","进口政策"]},
        {"id":"RUL_230","name":"动力煤限价政策","type":"政策规则","groundBase":"order","importance":10,
         "description":"发改委对动力煤实行价格区间调控，是市场定价的核心约束","trackingVariables":["限价区间","执行力度"]}
    ],
    "chains":[
        {"id":"C_250","name":"保供稳价压制煤价链","domain":"能源","groundBase":"order",
         "triggerEvent":"发改委启动保供稳价政策",
         "steps":[
             {"seq":1,"from":"煤价快速上涨","to":"发改委约谈/限价","confidence":"高","lag":"即时","mechanism":"价格触发政策干预"},
             {"seq":2,"from":"限价政策","to":"产能核增加速","confidence":"中","lag":"月度","mechanism":"审批加速释放产能"},
             {"seq":3,"from":"产能释放","to":"供应增加","confidence":"中","lag":"季度","mechanism":"新产能投产"},
             {"seq":4,"from":"供应增加","to":"煤价回落","confidence":"中","lag":"即时","mechanism":"供需改善压制价格"}
         ],"reversalNode":"政策放松","reversalCondition":"经济下行需要煤企增产",
         "polarityTensionThreshold":0.7,"historicalCases":[{"year":"2021","description":"煤价暴涨至2000+，发改委连续出台限价政策"}],
         "reversibility":0.6,"tail_probability":0.15,"minority_protected":False},
        {"id":"C_251","name":"电厂补库推升煤价链","domain":"能源","groundBase":"marginal",
         "triggerEvent":"夏季高温或冬季取暖用电高峰",
         "steps":[
             {"seq":1,"from":"高温/取暖需求","to":"电厂日耗上升","confidence":"高","lag":"即时","mechanism":"用电需求增加"},
             {"seq":2,"from":"日耗上升","to":"电厂库存下降","confidence":"高","lag":"1-2周","mechanism":"消耗快于补充"},
             {"seq":3,"from":"库存下降","to":"电厂补库采购增加","confidence":"高","lag":"即时","mechanism":"安全库存驱动补库"},
             {"seq":4,"from":"补库增加","to":"煤价上涨","confidence":"中","lag":"即时","mechanism":"需求推升价格"}
         ],"reversalNode":"需求回落","reversalCondition":"气温回落或用电需求下降",
         "polarityTensionThreshold":0.65,"historicalCases":[],"reversibility":0.7,"tail_probability":0.15,"minority_protected":False}
    ],
    "relations":[
        {"id":"R_600","type":"政策传导","from":"发改委限价政策","to":"动力煤价格","strength":0.9,"direction":"约束","groundBase":"order","stability":"高",
         "description":"限价政策是动力煤价格天花板，突破限价触发政策干预","reversalPoint":"限价政策调整或执行放松"},
        {"id":"R_601","type":"季节性规律","from":"夏季高温/冬季取暖","to":"动力煤需求","strength":0.8,"direction":"正向","groundBase":"natural","lag":"季节性",
         "description":"夏季空调用电和冬季取暖是动力煤需求峰值","reversalPoint":"暖冬/凉夏时季节性减弱"},
        {"id":"R_602","type":"库存传导","from":"电厂煤炭库存","to":"动力煤价格","strength":0.8,"direction":"反向","groundBase":"marginal","lag":"即时",
         "description":"电厂库存是供需平衡核心指标","reversalPoint":"库存低于安全线时补库推升价格"},
        {"id":"R_603","type":"进口传导","from":"进口煤量","to":"国内煤价","strength":0.65,"direction":"反向","groundBase":"marginal","lag":"月度",
         "description":"进口煤增加国内供应","reversalPoint":"进口政策变化"},
        {"id":"R_604","type":"运输传导","from":"铁路运力","to":"煤炭到港量","strength":0.7,"direction":"正向","groundBase":"natural","lag":"即时",
         "description":"大秦线等铁路运力制约煤炭到港量","reversalPoint":"运力瓶颈解除"}
    ],
    "polarity":{
        "秦皇岛5500大卡动力煤价":{"historicalMin":400,"historicalMax":2000,"recentMin":700,"recentMax":1200,
                                   "reversalSignalPatterns":["发改委政策","电厂库存","季节性需求","进口量"]}
    },
    "models":[
        {"id":"M_100","name":"动力煤的政策-供需定价模型","domain":"政策定价","groundBase":"order",
         "formula":"ZC_Price = min(PolicyCeiling, SupplyDemandEquilibrium)",
         "variables":[
             {"name":"发改委限价上限","id":"policy_ceiling","direction":"上限","weight":0.4},
             {"name":"供需基本面","id":"supply_demand","direction":"正向","weight":0.35},
             {"name":"季节性需求","id":"seasonal","direction":"正向","weight":0.15},
             {"name":"运输瓶颈","id":"logistics","direction":"正向","weight":0.1}
         ],
         "description":"动力煤定价核心是政策天花板vs供需基本面。限价政策是价格上限，供需决定实际价格水平。夏季/冬季需求峰值推升价格。",
         "dominantPhase":"供需紧张+政策干预频发期模型最有效",
         "limitation":"政策执行力度难以量化",
         "trackingVariables":["限价政策","电厂库存","日耗量","进口量"],
         "linkToEntities":["VAR_250","VAR_251"],
         "linkToRelations":["R_600","R_601","R_602"],
         "linkToConductionChains":["C_250","C_251"]}
    ]
}

# ==================== 尿素 ====================
urea = {
    "c":"尿素","s":"UR",
    "entities":[
        {"id":"GEO_320","name":"中国尿素产能","type":"供给节点","groundBase":"natural","importance":10,
         "description":"全球最大尿素生产国和消费国，煤制尿素占比约70%","controlledBy":["阳煤集团","晋煤集团","中海化学"],
         "trackingVariables":["总产能","开工率","煤制利润","气制利润"]},
        {"id":"GEO_321","name":"中东尿素产能","type":"供给节点","groundBase":"natural","importance":8,
         "description":"沙特/阿联酋/卡塔尔等中东国家，天然气制尿素成本低","trackingVariables":["出口量","报价"]},
        {"id":"POW_240","name":"郑州商品交易所CZCE","type":"交易所","groundBase":"rule","importance":10,
         "description":"中国尿素期货定价中心","jurisdiction":"中国","trackingVariables":["UR期价","持仓量"]},
        {"id":"VAR_260","name":"CZCE尿素期货价格","type":"大宗商品变量","groundBase":"marginal","importance":10,
         "currentValue":"约2000元/吨","historicalRange":{"min":1400,"max":3000},"recentRange":{"min":1600,"max":2600},"trackingFrequency":"实时"},
        {"id":"VAR_261","name":"尿素现货价格","type":"现货变量","groundBase":"marginal","importance":9,
         "trackingFrequency":"每日","trackingVariables":["山东价","河南价","出口价"]},
        {"id":"VAR_262","name":"尿素出口量","type":"贸易变量","groundBase":"marginal","importance":8,
         "trackingFrequency":"月度","trackingVariables":["出口量","出口检验政策"]},
        {"id":"VAR_263","name":"煤炭价格","type":"成本变量","groundBase":"marginal","importance":8,
         "trackingFrequency":"每日","trackingVariables":["无烟煤价格","动力煤价格"]},
        {"id":"CUL_240","name":"出口检验政策叙事","type":"政策共识","groundBase":"order","importance":7,
         "description":"中国尿素出口实行法定检验政策，检验周期和放松程度影响出口节奏","trackingVariables":["检验政策","出口量","国际价格"]},
        {"id":"RUL_240","name":"尿素出口法定检验政策","type":"贸易规则","groundBase":"order","importance":8,
         "description":"尿素出口需法定检验，检验周期影响出口节奏","trackingVariables":["检验政策","出口放行"]}
    ],
    "chains":[
        {"id":"C_260","name":"成本推升尿素链","domain":"化工","groundBase":"marginal",
         "triggerEvent":"煤炭价格大幅上涨推升尿素成本",
         "steps":[
             {"seq":1,"from":"煤价上涨","to":"尿素生产成本上升","confidence":"高","lag":"即时","mechanism":"煤占尿素成本约60-70%"},
             {"seq":2,"from":"成本上升","to":"尿素利润压缩","confidence":"高","lag":"即时","mechanism":"成本传导不畅"},
             {"seq":3,"from":"利润压缩","to":"开工率下降","confidence":"中","lag":"1-2周","mechanism":"亏损降负"},
             {"seq":4,"from":"开工下降","to":"尿素供应减少","confidence":"中","lag":"即时","mechanism":"产量下降"},
             {"seq":5,"from":"供应减少","to":"尿素价格受成本支撑","confidence":"中","lag":"即时","mechanism":"成本+供给支撑"}
         ],"reversalNode":"煤价回落","reversalCondition":"煤炭价格回落改善利润",
         "polarityTensionThreshold":0.6,"historicalCases":[],"reversibility":0.7,"tail_probability":0.15,"minority_protected":False},
        {"id":"C_261","name":"春耕旺季推升尿素链","domain":"化工","groundBase":"natural",
         "triggerEvent":"春季施肥旺季到来",
         "steps":[
             {"seq":1,"from":"春耕季节","to":"农业用肥需求增加","confidence":"高","lag":"季节性","mechanism":"农业生产季节性"},
             {"seq":2,"from":"需求增加","to":"尿素采购放量","confidence":"高","lag":"即时","mechanism":"下游集中采购"},
             {"seq":3,"from":"采购放量","to":"库存去化","confidence":"高","lag":"2-4周","mechanism":"需求拉动去库"},
             {"seq":4,"from":"去库","to":"尿素价格上涨","confidence":"中","lag":"即时","mechanism":"供需收紧"}
         ],"reversalNode":"旺季结束","reversalCondition":"施肥季结束",
         "polarityTensionThreshold":0.6,"historicalCases":[],"reversibility":0.7,"tail_probability":0.15,"minority_protected":False}
    ],
    "relations":[
        {"id":"R_620","type":"成本传导","from":"煤炭价格","to":"尿素成本","strength":0.85,"direction":"正向","groundBase":"marginal","lag":"即时",
         "description":"煤占尿素成本约60-70%","reversalPoint":"气制尿素占比提升"},
        {"id":"R_621","type":"季节性规律","from":"春耕旺季","to":"尿素需求","strength":0.8,"direction":"正向","groundBase":"natural","lag":"季节性",
         "description":"春季施肥是尿素年度需求峰值","reversalPoint":"旺季不旺时季节性落空"},
        {"id":"R_622","type":"出口传导","from":"出口检验政策","to":"尿素出口量","strength":0.75,"direction":"复杂","groundBase":"order","lag":"月度",
         "description":"检验政策放松增加出口，收紧减少出口","reversalPoint":"政策调整"},
        {"id":"R_623","type":"库存传导","from":"尿素企业库存","to":"尿素价格","strength":0.7,"direction":"反向","groundBase":"marginal","lag":"即时",
         "description":"库存是供需平衡指标","reversalPoint":"库存极低时价格弹性增大"}
    ],
    "polarity":{
        "CZCE尿素期货价格":{"historicalMin":1400,"historicalMax":3000,"recentMin":1600,"recentMax":2600,
                            "reversalSignalPatterns":["煤炭价格变化","春耕旺季启动","出口政策变化","库存变化"]}
    },
    "models":[
        {"id":"M_105","name":"尿素的成本-季节性定价模型","domain":"产业链定价","groundBase":"marginal",
         "formula":"UR_Score = w1*CoalCostFactor + w2*SeasonalFactor + w3*ExportFactor + w4*InventoryFactor",
         "variables":[
             {"name":"煤炭成本因子","id":"coal_cost","direction":"正向","weight":0.35},
             {"name":"季节性需求因子","id":"seasonal","direction":"正向","weight":0.3},
             {"name":"出口因子","id":"export","direction":"正向","weight":0.2},
             {"name":"库存因子","id":"inventory","direction":"反向","weight":0.15}
         ],
         "description":"尿素定价以煤炭成本为锚，春耕需求为季节性峰值，出口为边际增量。限价政策约束价格上限。",
         "dominantPhase":"春耕旺季+煤价上涨时价格弹性最大",
         "limitation":"出口检验政策变化难以预测",
         "trackingVariables":["煤炭成本","春耕需求","出口量","库存"],
         "linkToEntities":["VAR_260","VAR_262","VAR_263"],
         "linkToRelations":["R_620","R_621","R_622"],
         "linkToConductionChains":["C_260","C_261"]}
    ]
}

# ==================== 乙二醇 ====================
eg = {
    "c":"乙二醇","s":"EG",
    "entities":[
        {"id":"GEO_330","name":"中国乙二醇产能","type":"供给节点","groundBase":"natural","importance":9,
         "description":"中国乙二醇产能约2500万吨/年，煤制乙二醇是重要补充路线","trackingVariables":["总产能","开工率","煤制利润"]},
        {"id":"GEO_331","name":"中东乙二醇产能","type":"供给节点","groundBase":"natural","importance":8,
         "description":"沙特/科威特等中东国家，乙烷裂解副产乙二醇成本低","trackingVariables":["出口量","报价"]},
        {"id":"POW_250","name":"大连商品交易所DCE","type":"交易所","groundBase":"rule","importance":10,
         "description":"中国乙二醇期货定价中心","jurisdiction":"中国","trackingVariables":["EG期价","持仓量"]},
        {"id":"VAR_270","name":"DCE乙二醇期货价格","type":"大宗商品变量","groundBase":"marginal","importance":10,
         "currentValue":"约4500元/吨","historicalRange":{"min":3000,"max":7000},"recentRange":{"min":3500,"max":6000},"trackingFrequency":"实时"},
        {"id":"VAR_271","name":"乙二醇港口库存","type":"库存变量","groundBase":"marginal","importance":8,
         "trackingFrequency":"每周","trackingVariables":["港口库存","企业库存"]},
        {"id":"VAR_272","name":"乙二醇进口量","type":"贸易变量","groundBase":"marginal","importance":7,
         "trackingFrequency":"月度","trackingVariables":["进口到港量","进口利润"]},
        {"id":"CUL_250","name":"EG产能过剩叙事","type":"市场共识","groundBase":"culture","importance":7,
         "description":"乙二醇产能持续扩张，煤制路线增加供应弹性，行业利润中枢下移","trackingVariables":["新增产能","开工率","利润"]}
    ],
    "chains":[
        {"id":"C_270","name":"原油-石脑油-EG成本传导链","domain":"化工","groundBase":"marginal",
         "triggerEvent":"原油价格大幅波动",
         "steps":[
             {"seq":1,"from":"原油价格变化","to":"石脑油价格变化","confidence":"高","lag":"即时","mechanism":"成本传导"},
             {"seq":2,"from":"石脑油变化","to":"EG生产成本变化","confidence":"高","lag":"即时","mechanism":"油制EG路线"},
             {"seq":3,"from":"成本变化","to":"EG价格联动","confidence":"中","lag":"即时","mechanism":"成本推升价格"}
         ],"reversalNode":"原油回落","reversalCondition":"原油价格回落",
         "polarityTensionThreshold":0.6,"historicalCases":[],"reversibility":0.7,"tail_probability":0.15,"minority_protected":False}
    ],
    "relations":[
        {"id":"R_640","type":"原油传导","from":"原油价格","to":"EG价格","strength":0.75,"direction":"正向","groundBase":"marginal","lag":"即时",
         "description":"油制EG路线成本传导","reversalPoint":"煤制占比提升后传导减弱"},
        {"id":"R_641","type":"库存传导","from":"EG港口库存","to":"EG价格","strength":0.7,"direction":"反向","groundBase":"marginal","lag":"即时",
         "description":"库存是供需平衡指标","reversalPoint":"库存极低时价格弹性增大"},
        {"id":"R_642","type":"产能周期","from":"EG新增产能","to":"EG价格中枢","strength":0.7,"direction":"反向","groundBase":"marginal","lag":"季度",
         "description":"产能扩张压制利润中枢","reversalPoint":"需求增速超产能增速"},
        {"id":"R_643","type":"下游需求","from":"聚酯开工率","to":"EG需求","strength":0.75,"direction":"正向","groundBase":"marginal","lag":"即时",
         "description":"聚酯是EG最大下游，开工率反映需求强度","reversalPoint":"聚酯利润压缩时降负"}
    ],
    "polarity":{
        "DCE乙二醇期货价格":{"historicalMin":3000,"historicalMax":7000,"recentMin":3500,"recentMax":6000,
                              "reversalSignalPatterns":["原油价格波动","聚酯需求变化","库存变化","新增产能投产"]}
    },
    "models":[
        {"id":"M_110","name":"乙二醇的成本-供需定价模型","domain":"产业链定价","groundBase":"marginal",
         "formula":"EG_Score = w1*CrudeFactor + w2*InventoryFactor + w3*DemandFactor + w4*CapacityFactor",
         "variables":[
             {"name":"原油成本因子","id":"crude","direction":"正向","weight":0.35},
             {"name":"库存因子","id":"inventory","direction":"反向","weight":0.25},
             {"name":"聚酯需求因子","id":"demand","direction":"正向","weight":0.25},
             {"name":"产能扩张因子","id":"capacity","direction":"反向","weight":0.15}
         ],
         "description":"EG定价以原油为成本锚，聚酯需求为驱动，产能过剩压制利润。煤制路线增加供应弹性。",
         "dominantPhase":"聚酯旺季+库存低位时弹性最大",
         "limitation":"煤制路线定价逻辑与油制不同",
         "trackingVariables":["原油价格","港口库存","聚酯开工率","新增产能"],
         "linkToEntities":["VAR_270","VAR_271"],
         "linkToRelations":["R_640","R_641","R_642","R_643"],
         "linkToConductionChains":["C_270"]}
    ]
}

# ==================== 沥青 ====================
asphalt = {
    "c":"沥青","s":"BU",
    "entities":[
        {"id":"GEO_340","name":"中国沥青产能","type":"供给节点","groundBase":"natural","importance":9,
         "description":"中国沥青产能约8000万吨/年，中石化/中石油主导","trackingVariables":["总产能","开工率","产量"]},
        {"id":"POW_260","name":"上海期货交易所SHFE","type":"交易所","groundBase":"rule","importance":10,
         "description":"中国沥青期货定价中心","jurisdiction":"中国","trackingVariables":["BU期价","持仓量"]},
        {"id":"VAR_280","name":"SHFE沥青期货价格","type":"大宗商品变量","groundBase":"marginal","importance":10,
         "currentValue":"约3600元/吨","historicalRange":{"min":1800,"max":5500},"recentRange":{"min":2800,"max":4800},"trackingFrequency":"实时"},
        {"id":"VAR_281","name":"沥青炼厂开工率","type":"供给变量","groundBase":"marginal","importance":8,
         "trackingFrequency":"每周","trackingVariables":["炼厂开工率","沥青产量"]},
        {"id":"VAR_282","name":"道路沥青需求","type":"需求变量","groundBase":"marginal","importance":8,
         "trackingFrequency":"月度","trackingVariables":["公路投资","道路开工","防水卷材"]},
        {"id":"CUL_260","name":"基建拉动沥青需求叙事","type":"市场共识","groundBase":"culture","importance":7,
         "description":"沥青主要用于道路建设，基建投资是需求核心驱动","trackingVariables":["公路投资","专项债","项目开工"]}
    ],
    "chains":[
        {"id":"C_280","name":"原油-沥青成本传导链","domain":"能源","groundBase":"marginal",
         "triggerEvent":"原油价格大幅波动",
         "steps":[
             {"seq":1,"from":"原油价格变化","to":"沥青生产成本变化","confidence":"高","lag":"即时","mechanism":"沥青是炼厂副产品"},
             {"seq":2,"from":"成本变化","to":"沥青价格联动","confidence":"中","lag":"即时","mechanism":"成本传导"}
         ],"reversalNode":"原油回落","reversalCondition":"原油价格回落",
         "polarityTensionThreshold":0.6,"historicalCases":[],"reversibility":0.7,"tail_probability":0.15,"minority_protected":False},
        {"id":"C_281","name":"基建需求推升沥青链","domain":"能源","groundBase":"marginal",
         "triggerEvent":"基建投资加码",
         "steps":[
             {"seq":1,"from":"基建投资加码","to":"道路项目开工增加","confidence":"高","lag":"季度","mechanism":"投资转化为项目"},
             {"seq":2,"from":"项目开工","to":"沥青需求增加","confidence":"高","lag":"即时","mechanism":"道路施工消耗沥青"},
             {"seq":3,"from":"需求增加","to":"沥青库存去化","confidence":"高","lag":"月度","mechanism":"需求拉动去库"},
             {"seq":4,"from":"去库","to":"沥青价格上涨","confidence":"中","lag":"即时","mechanism":"供需收紧"}
         ],"reversalNode":"基建投资放缓","reversalCondition":"专项债发行放缓或项目完工",
         "polarityTensionThreshold":0.6,"historicalCases":[],"reversibility":0.6,"tail_probability":0.15,"minority_protected":False}
    ],
    "relations":[
        {"id":"R_660","type":"原油传导","from":"原油价格","to":"沥青价格","strength":0.85,"direction":"正向","groundBase":"marginal","lag":"即时",
         "description":"沥青是炼厂副产品，原油是核心成本","reversalPoint":"沥青自身供需紧张时可脱钩"},
        {"id":"R_661","type":"季节性规律","from":"道路施工旺季","to":"沥青需求","strength":0.75,"direction":"正向","groundBase":"natural","lag":"季节性",
         "description":"4-10月是道路施工旺季","reversalPoint":"雨季/寒冬施工减少"},
        {"id":"R_662","type":"政策传导","from":"基建投资","to":"沥青需求","strength":0.7,"direction":"正向","groundBase":"order","lag":"季度",
         "description":"基建投资是沥青需求核心驱动","reversalPoint":"投资增速放缓"},
        {"id":"R_663","type":"库存传导","from":"沥青社会库存","to":"沥青价格","strength":0.7,"direction":"反向","groundBase":"marginal","lag":"即时",
         "description":"库存是供需平衡指标","reversalPoint":"库存极低时价格弹性增大"}
    ],
    "polarity":{
        "SHFE沥青期货价格":{"historicalMin":1800,"historicalMax":5500,"recentMin":2800,"recentMax":4800,
                            "reversalSignalPatterns":["原油价格波动","基建投资启动","施工旺季","库存变化"]}
    },
    "models":[
        {"id":"M_115","name":"沥青的成本-需求定价模型","domain":"产业链定价","groundBase":"marginal",
         "formula":"BU_Score = w1*CrudeFactor + w2*InfraFactor + w3*SeasonalFactor + w4*InventoryFactor",
         "variables":[
             {"name":"原油成本因子","id":"crude","direction":"正向","weight":0.45},
             {"name":"基建投资因子","id":"infra","direction":"正向","weight":0.25},
             {"name":"季节性因子","id":"seasonal","direction":"正向","weight":0.15},
             {"name":"库存因子","id":"inventory","direction":"反向","weight":0.15}
         ],
         "description":"沥青定价以原油为成本锚，基建投资为需求驱动。施工旺季推升需求。",
         "dominantPhase":"施工旺季+基建投资加码时弹性最大",
         "limitation":"沥青裂解价差波动大",
         "trackingVariables":["原油价格","基建投资","施工旺季","库存"],
         "linkToEntities":["VAR_280","VAR_282"],
         "linkToRelations":["R_660","R_661","R_662"],
         "linkToConductionChains":["C_280","C_281"]}
    ]
}

# ==================== 玻璃 ====================
glass = {
    "c":"玻璃","s":"FG",
    "entities":[
        {"id":"GEO_350","name":"河北沙河玻璃产业集群","type":"消费节点","groundBase":"natural","importance":10,
         "description":"中国最大玻璃现货市场，沙河价格是国内定价锚","trackingVariables":["产能","开工率","现货价","库存"]},
        {"id":"GEO_351","name":"华南玻璃产区","type":"消费节点","groundBase":"natural","importance":8,
         "description":"广东/福建玻璃产能集中区","trackingVariables":["产能","开工率"]},
        {"id":"POW_270","name":"郑州商品交易所CZCE","type":"交易所","groundBase":"rule","importance":10,
         "description":"中国玻璃期货定价中心","jurisdiction":"中国","trackingVariables":["FG期价","持仓量"]},
        {"id":"VAR_290","name":"CZCE玻璃期货价格","type":"大宗商品变量","groundBase":"marginal","importance":10,
         "currentValue":"约1500元/吨","historicalRange":{"min":800,"max":3000},"recentRange":{"min":1100,"max":2500},"trackingFrequency":"实时"},
        {"id":"VAR_291","name":"玻璃现货价格（沙河）","type":"现货变量","groundBase":"marginal","importance":9,
         "trackingFrequency":"每日","trackingVariables":["沙河价","华南价","期现基差"]},
        {"id":"VAR_292","name":"玻璃企业库存","type":"库存变量","groundBase":"marginal","importance":9,
         "trackingFrequency":"每周","trackingVariables":["企业库存天数","社会库存"]},
        {"id":"VAR_293","name":"房地产竣工面积","type":"需求变量","groundBase":"marginal","importance":9,
         "trackingFrequency":"月度","trackingVariables":["竣工面积","新开工面积","销售面积"]},
        {"id":"CUL_270","name":"房地产驱动玻璃需求叙事","type":"市场共识","groundBase":"culture","importance":8,
         "description":"玻璃约70%用于房地产竣工端，竣工面积是需求核心驱动","trackingVariables":["竣工面积","保交楼政策","房地产销售"]}
    ],
    "chains":[
        {"id":"C_290","name":"房地产竣工驱动玻璃需求链","domain":"建材","groundBase":"marginal",
         "triggerEvent":"房地产竣工面积大幅增长",
         "steps":[
             {"seq":1,"from":"竣工面积增长","to":"玻璃安装需求增加","confidence":"高","lag":"即时","mechanism":"竣工交付消耗玻璃"},
             {"seq":2,"from":"需求增加","to":"玻璃库存去化","confidence":"高","lag":"2-4周","mechanism":"需求拉动去库"},
             {"seq":3,"from":"去库","to":"玻璃价格上涨","confidence":"高","lag":"即时","mechanism":"供需收紧推升价格"},
             {"seq":4,"from":"价格上涨","to":"玻璃利润改善","confidence":"高","lag":"即时","mechanism":"利润修复"},
             {"seq":5,"from":"利润改善","to":"复产点火增加","confidence":"中","lag":"1-3个月","mechanism":"利润驱动产能恢复"}
         ],"reversalNode":"竣工放缓","reversalCondition":"房地产竣工面积回落",
         "polarityTensionThreshold":0.7,"historicalCases":[{"year":"2021","description":"竣工大年，玻璃从1800涨至3000"}],
         "reversibility":0.6,"tail_probability":0.2,"minority_protected":False},
        {"id":"C_291","name":"冷修减产推升玻璃链","domain":"建材","groundBase":"marginal",
         "triggerEvent":"玻璃行业持续亏损触发冷修潮",
         "steps":[
             {"seq":1,"from":"持续亏损","to":"产线冷修增加","confidence":"高","lag":"月度","mechanism":"亏损被迫冷修"},
             {"seq":2,"from":"冷修增加","to":"在产产能下降","confidence":"高","lag":"即时","mechanism":"产能退出"},
             {"seq":3,"from":"产能下降","to":"供应减少","confidence":"高","lag":"即时","mechanism":"产量下降"},
             {"seq":4,"from":"供应减少","to":"价格企稳回升","confidence":"中","lag":"月度","mechanism":"供需改善"}
         ],"reversalNode":"利润恢复复产","reversalCondition":"价格回升至盈利线以上",
         "polarityTensionThreshold":0.65,"historicalCases":[],"reversibility":0.5,"tail_probability":0.15,"minority_protected":False}
    ],
    "relations":[
        {"id":"R_680","type":"需求传导","from":"房地产竣工面积","to":"玻璃需求","strength":0.85,"direction":"正向","groundBase":"marginal","lag":"季度",
         "description":"玻璃约70%用于房地产竣工端","reversalPoint":"竣工与新开工脱钩"},
        {"id":"R_681","type":"库存传导","from":"玻璃企业库存","to":"玻璃价格","strength":0.8,"direction":"反向","groundBase":"marginal","lag":"即时",
         "description":"库存是供需平衡最直接指标","reversalPoint":"库存低于安全线时价格弹性增大"},
        {"id":"R_682","type":"成本传导","from":"纯碱价格","to":"玻璃成本","strength":0.65,"direction":"正向","groundBase":"marginal","lag":"即时",
         "description":"纯碱占玻璃成本约25-30%","reversalPoint":"纯碱过剩价格下跌"},
        {"id":"R_683","type":"季节性规律","from":"金九银十","to":"玻璃需求","strength":0.7,"direction":"正向","groundBase":"natural","lag":"季节性",
         "description":"秋季是房地产竣工和玻璃消费旺季","reversalPoint":"旺季不旺"},
        {"id":"R_684","type":"产能周期","from":"玻璃产线冷修/复产","to":"玻璃供应","strength":0.75,"direction":"复杂","groundBase":"marginal","lag":"月度",
         "description":"冷修减少供应，复产增加供应","reversalPoint":"冷修后复产需要3-6个月"}
    ],
    "polarity":{
        "CZCE玻璃期货价格":{"historicalMin":800,"historicalMax":3000,"recentMin":1100,"recentMax":2500,
                            "reversalSignalPatterns":["房地产竣工数据","库存变化","冷修/复产","纯碱价格"]}
    },
    "models":[
        {"id":"M_120","name":"玻璃的房地产周期定价模型","domain":"需求定价","groundBase":"marginal",
         "formula":"FG_Score = w1*CompletionFactor + w2*InventoryFactor + w3*CostFactor + w4*CapacityFactor",
         "variables":[
             {"name":"房地产竣工因子","id":"completion","direction":"正向","weight":0.4},
             {"name":"库存因子","id":"inventory","direction":"反向","weight":0.3},
             {"name":"纯碱成本因子","id":"cost","direction":"正向","weight":0.15},
             {"name":"产能变化因子","id":"capacity","direction":"复杂","weight":0.15}
         ],
         "description":"玻璃定价以房地产竣工为核心驱动，库存为供需指标。冷修/复产是供给端弹性。",
         "dominantPhase":"竣工大年+库存低位时价格弹性最大",
         "limitation":"房地产周期变化使竣工预测困难",
         "trackingVariables":["竣工面积","库存","纯碱价格","产线变化"],
         "linkToEntities":["VAR_290","VAR_292","VAR_293"],
         "linkToRelations":["R_680","R_681","R_682"],
         "linkToConductionChains":["C_290","C_291"]}
    ]
}

# ==================== 纯碱 ====================
soda_ash = {
    "c":"纯碱","s":"SA",
    "entities":[
        {"id":"GEO_360","name":"中国纯碱产能","type":"供给节点","groundBase":"natural","importance":10,
         "description":"全球最大纯碱生产国，氨碱法/联碱法/天然碱法并存","trackingVariables":["总产能","开工率","各工艺利润"]},
        {"id":"GEO_361","name":"河南天然碱矿区","type":"资源节点","groundBase":"natural","importance":8,
         "description":"中国天然碱核心产区，桐柏碱矿为代表","trackingVariables":["产量","成本"]},
        {"id":"POW_280","name":"郑州商品交易所CZCE","type":"交易所","groundBase":"rule","importance":10,
         "description":"中国纯碱期货定价中心","jurisdiction":"中国","trackingVariables":["SA期价","持仓量"]},
        {"id":"VAR_300","name":"CZCE纯碱期货价格","type":"大宗商品变量","groundBase":"marginal","importance":10,
         "currentValue":"约1800元/吨","historicalRange":{"min":1200,"max":3500},"recentRange":{"min":1400,"max":2800},"trackingFrequency":"实时"},
        {"id":"VAR_301","name":"纯碱企业库存","type":"库存变量","groundBase":"marginal","importance":9,
         "trackingFrequency":"每周","trackingVariables":["企业库存","社会库存"]},
        {"id":"VAR_302","name":"浮法玻璃产能","type":"需求变量","groundBase":"marginal","importance":8,
         "trackingFrequency":"每周","trackingVariables":["浮法在产产能","日熔量"]},
        {"id":"VAR_303","name":"光伏玻璃产能","type":"需求变量","groundBase":"marginal","importance":8,
         "trackingFrequency":"月度","trackingVariables":["光伏玻璃产能","投产进度"]},
        {"id":"CUL_280","name":"光伏玻璃拉动纯碱需求叙事","type":"市场共识","groundBase":"culture","importance":8,
         "description":"光伏玻璃是纯碱需求最大增量，每GW光伏玻璃消耗约1万吨纯碱","trackingVariables":["光伏装机","光伏玻璃投产","纯碱需求增量"]}
    ],
    "chains":[
        {"id":"C_300","name":"光伏玻璃扩产拉动纯碱链","domain":"化工","groundBase":"marginal",
         "triggerEvent":"光伏玻璃产能集中投产",
         "steps":[
             {"seq":1,"from":"光伏玻璃投产","to":"纯碱需求增加","confidence":"高","lag":"即时","mechanism":"每GW光伏玻璃消耗约1万吨纯碱"},
             {"seq":2,"from":"需求增加","to":"纯碱库存去化","confidence":"高","lag":"月度","mechanism":"需求拉动去库"},
             {"seq":3,"from":"去库","to":"纯碱价格上涨","confidence":"中","lag":"即时","mechanism":"供需收紧"}
         ],"reversalNode":"光伏玻璃投产放缓","reversalCondition":"光伏玻璃产能过剩",
         "polarityTensionThreshold":0.65,"historicalCases":[{"year":"2022","description":"光伏玻璃大投产，纯碱从2000涨至3000"}],
         "reversibility":0.6,"tail_probability":0.15,"minority_protected":False}
    ],
    "relations":[
        {"id":"R_700","type":"需求传导","from":"浮法玻璃产能","to":"纯碱需求","strength":0.8,"direction":"正向","groundBase":"marginal","lag":"即时",
         "description":"浮法玻璃是纯碱最大传统下游","reversalPoint":"玻璃冷修减少需求"},
        {"id":"R_701","type":"需求增量","from":"光伏玻璃投产","to":"纯碱需求","strength":0.75,"direction":"正向","groundBase":"marginal","lag":"季度",
         "description":"光伏玻璃是纯碱最大需求增量","reversalPoint":"光伏玻璃产能过剩"},
        {"id":"R_702","type":"库存传导","from":"纯碱企业库存","to":"纯碱价格","strength":0.8,"direction":"反向","groundBase":"marginal","lag":"即时",
         "description":"库存是供需平衡核心指标","reversalPoint":"库存极低时价格弹性急剧放大"},
        {"id":"R_703","type":"产能周期","from":"纯碱新增产能","to":"纯碱价格","strength":0.7,"direction":"反向","groundBase":"marginal","lag":"季度",
         "description":"天然碱等新增产能压制价格","reversalPoint":"需求增速超产能增速"}
    ],
    "polarity":{
        "CZCE纯碱期货价格":{"historicalMin":1200,"historicalMax":3500,"recentMin":1400,"recentMax":2800,
                            "reversalSignalPatterns":["光伏玻璃投产","浮法玻璃变化","库存变化","新增产能"]}
    },
    "models":[
        {"id":"M_125","name":"纯碱的需求-库存定价模型","domain":"需求定价","groundBase":"marginal",
         "formula":"SA_Score = w1*GlassFactor + w2*PV_Factor + w3*InventoryFactor + w4*CapacityFactor",
         "variables":[
             {"name":"浮法玻璃需求因子","id":"glass","direction":"正向","weight":0.35},
             {"name":"光伏玻璃需求因子","id":"PV_glass","direction":"正向","weight":0.3},
             {"name":"库存因子","id":"inventory","direction":"反向","weight":0.25},
             {"name":"新增产能因子","id":"capacity","direction":"反向","weight":0.1}
         ],
         "description":"纯碱定价以玻璃需求为核心驱动，光伏玻璃为增量，库存为供需指标。",
         "dominantPhase":"光伏玻璃投产+库存低位时弹性最大",
         "limitation":"产能投放节奏难以预测",
         "trackingVariables":["玻璃产能","光伏玻璃投产","库存","新增产能"],
         "linkToEntities":["VAR_300","VAR_301","VAR_302","VAR_303"],
         "linkToRelations":["R_700","R_701","R_702"],
         "linkToConductionChains":["C_300"]}
    ]
}

# ==================== 运行 ====================
if __name__ == "__main__":
    products = {
        "apple": apple,
        "thermal_coal": thermal_coal,
        "urea": urea,
        "eg": eg,
        "asphalt": asphalt,
        "glass": glass,
        "soda_ash": soda_ash,
    }
    print(f"Generating {len(products)} products...")
    for name, data in products.items():
        w(name, data)
    print("Done!")
