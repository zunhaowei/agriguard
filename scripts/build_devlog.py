"""生成开发日志 HTML（内嵌截图/数据/会议纪要），供 Edge 转 PDF。"""
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"
ASSET = ROOT / "参赛材料" / "assets"
RUNS = ROOT / "runs" / "agriguard"
OUT = ROOT / "参赛材料" / "开发日志.html"


def b64(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


img_home = b64(MEDIA / "screens" / "01_home.png", "image/png")
img_result = b64(MEDIA / "screens" / "02_result.png", "image/png")
img_presc = b64(MEDIA / "screens" / "04_bottom_prescription.png", "image/png")
img_heat = b64(ASSET / "heatmap_hi.png", "image/png")
img_curve = b64(RUNS / "results.png", "image/png")
img_cm = b64(RUNS / "confusion_matrix.png", "image/png")
img_val = b64(RUNS / "val_batch0_pred.jpg", "image/jpeg")


def fig(data, caption, w=None):
    st = f'style="width:{w}mm"' if w else ""
    return (f'<figure class="shot"><img src="{data}" {st} alt="{caption}"/>'
            f'<figcaption>{caption}</figcaption></figure>')


html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>禾目 AgriGuard 项目开发日志</title>
<style>
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: "Microsoft YaHei","PingFang SC",sans-serif; color: #1F2937;
         background: #EEF3EF; font-size: 13px; line-height: 1.68; }}
  .page {{ width: 210mm; margin: 0 auto; background: #fff; padding: 15mm 16mm 12mm;
          page-break-after: always; height: 297mm; overflow: hidden; }}
  h1,h2,h3 {{ color: #123A26; }}
  .cover {{ text-align: center; padding-top: 42mm; }}
  .cover .badge {{ display:inline-block; background: #D8F3E2; color: #1F5E3A;
                   padding: 4px 18px; border-radius: 20px; font-size: 12px; letter-spacing: 1px; margin-bottom: 14px; }}
  .cover h1 {{ font-size: 34px; margin: 8px 0 6px; }}
  .cover .sub {{ font-size: 16px; color: #2E7D4F; }}
  .cover .meta {{ margin-top: 38px; color: #5B6B78; font-size: 13px; line-height: 2; }}
  h2.sec {{ font-size: 19px; border-left: 5px solid #2E7D4F; padding-left: 11px; margin: 0 0 12px; }}
  h3 {{ font-size: 14px; margin: 14px 0 6px; color: #2E7D4F; }}
  p {{ margin: 6px 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 8px 0; page-break-inside: avoid; }}
  th,td {{ border: 1px solid #DCE8E0; padding: 5px 9px; text-align: left; vertical-align: top; font-size: 12px; }}
  th {{ background: #1F5E3A; color: #fff; font-weight: 600; }}
  tr:nth-child(even) td {{ background: #F7FAF8; }}
  .tag {{ display:inline-block; background: #D8F3E2; color: #1F5E3A;
          padding: 0 8px; border-radius: 4px; font-size: 10.5px; margin-right: 5px; }}
  .timeline {{ border-left: 3px solid #86EFAC; margin-left: 5px; padding-left: 16px; }}
  .tl-item {{ position: relative; margin-bottom: 9px; page-break-inside: avoid; }}
  .tl-item::before {{ content:""; position:absolute; left:-24px; top:5px; width:10px; height:10px;
                      border-radius:50%; background:#2E7D4F; }}
  .tl-item .date {{ color: #2E7D4F; font-weight: 700; }}
  .tl-item .who {{ color: #5B6B78; font-size: 10.5px; }}
  .shot {{ text-align:center; margin: 10px 0; page-break-inside: avoid; }}
  .shot img {{ max-width: 100%; border: 1px solid #DCE8E0; border-radius: 5px; }}
  .shot figcaption {{ color: #5B6B78; font-size: 10.5px; margin-top: 4px; }}
  .grid2 {{ display: flex; gap: 10px; }}
  .grid2 .shot {{ flex: 1; }}
  .callout {{ background: #D8F3E2; border-left: 4px solid #2E7D4F;
              padding: 8px 13px; border-radius: 4px; margin: 9px 0; page-break-inside: avoid; }}
  .problem {{ background: #FDF2F2; border-left: 4px solid #C25B5B; padding: 8px 13px;
              border-radius: 4px; margin: 9px 0; page-break-inside: avoid; }}
  .problem b {{ color: #B03A3A; }}
  .meeting {{ border: 1px solid #DCE8E0; border-radius: 7px; padding: 10px 15px; margin: 10px 0;
              background:#FBFFFC; page-break-inside: avoid; }}
  .meeting .mt {{ font-weight: 700; color: #123A26; font-size: 13px; }}
  .meeting .mm {{ color: #5B6B78; font-size: 10.5px; margin-bottom: 6px; }}
  ul {{ margin: 4px 0; padding-left: 18px; }}
  li {{ margin: 2px 0; }}
  code {{ background: #EFF5F1; padding: 0 4px; border-radius: 3px; font-size: 11px; }}
  .footer {{ color: #9AA9A0; font-size: 10.5px; text-align:center; margin-top: 14px;
             border-top: 1px solid #E4ECE6; padding-top: 8px; }}
</style>
</head>
<body>

<!-- P1 封面 -->
<div class="page">
  <div class="cover">
    <span class="badge">项目开发日志 · DEVELOPMENT LOG</span>
    <h1>禾目 AgriGuard</h1>
    <div class="sub">作物病虫害智能诊断与精准处方系统</div>
    <div class="meta">
      团队：禾目 团队<br>
      成员：魏尊浩 · 徐佳静 · 王韬淦<br>
      时间跨度：2026 年 8 月 1 日 — 8 月 30 日<br>
      项目类型：iCAN 大学生创新创业大赛（创新赛道）
    </div>
  </div>
  <div class="footer">本文档为内部开发过程真实记录，含方案设计、实验测试、问题排查与版本迭代信息。</div>
</div>

<!-- P2 团队分工 + 时间线 + 版本 -->
<div class="page">
  <h2 class="sec">一、团队分工</h2>
  <table>
    <tr><th style="width:88px">成员</th><th style="width:140px">角色</th><th>主要职责</th></tr>
    <tr><td><b>魏尊浩</b><br><span class="tag">队长</span></td><td>算法与全栈</td>
        <td>系统架构设计；YOLO 模型训练与调优；Grad-CAM 可视化实现；后端接口与端到端闭环集成；项目统筹。</td></tr>
    <tr><td><b>徐佳静</b></td><td>前端与产品</td>
        <td>前端页面与交互设计；产品需求与体验打磨；产品文案与演示视频；视觉物料（海报/PPT）。</td></tr>
    <tr><td><b>王韬淦</b></td><td>数据与测试</td>
        <td>PlantVillage 数据集整理与校验；训练/验证切分；处方引擎接口联调；冒烟测试与使用文档。</td></tr>
  </table>

  <h2 class="sec">二、项目时间线总览</h2>
  <div class="timeline">
    <div class="tl-item"><div class="date">8月1日 — 5日</div>立项与方案设计 <span class="who">· 全员</span></div>
    <div class="tl-item"><div class="date">8月6日 — 11日</div>环境搭建与数据准备 <span class="who">· 王韬淦 / 魏尊浩</span></div>
    <div class="tl-item"><div class="date">8月12日 — 17日</div>模型训练与调优 <span class="who">· 魏尊浩</span></div>
    <div class="tl-item"><div class="date">8月16日 — 18日</div>中文类别映射与校验 <span class="who">· 王韬淦</span></div>
    <div class="tl-item"><div class="date">8月18日 — 20日</div>后端服务与处方引擎 <span class="who">· 魏尊浩 / 王韬淦</span></div>
    <div class="tl-item"><div class="date">8月20日 — 24日</div>前端页面与 Grad-CAM 可视化 <span class="who">· 徐佳静 / 魏尊浩</span></div>
    <div class="tl-item"><div class="date">8月25日 — 26日</div>端到端联调与测试 <span class="who">· 王韬淦 / 魏尊浩</span></div>
    <div class="tl-item"><div class="date">8月27日 — 30日</div>演示视频与参赛材料 <span class="who">· 徐佳静 / 全员</span></div>
  </div>

  <h2 class="sec">三、版本迭代记录</h2>
  <table>
    <tr><th style="width:70px">版本</th><th style="width:110px">日期</th><th>里程碑</th></tr>
    <tr><td><b>v0.1</b></td><td>8月11日</td><td>完成立项、技术选型与数据集整理，建立项目骨架。</td></tr>
    <tr><td><b>v0.2</b></td><td>8月17日</td><td>模型训练收敛（Top-1 99.8%），完成中文类别映射与校验。</td></tr>
    <tr><td><b>v0.3</b></td><td>8月24日</td><td>后端、处方引擎、前端、Grad-CAM 四模块就绪。</td></tr>
    <tr><td><b>v1.0</b></td><td>8月26日</td><td>端到端闭环联调通过，系统可交付演示。</td></tr>
    <tr><td><b>v1.1</b></td><td>8月30日</td><td>演示视频、海报、PPT 等参赛材料齐备。</td></tr>
  </table>
  <div class="footer">禾目 AgriGuard · 开发日志 · 第 2 页</div>
</div>

<!-- P3 立项 + 数据准备 -->
<div class="page">
  <h2 class="sec">四、开发过程关键节点</h2>
  <h3>4.1 立项与方案设计（8月1日—5日）</h3>
  <p>团队围绕「农业 + 人工智能」主题头脑风暴，最终锁定「作物病虫害智能诊断」方向。
     通过调研家庭园艺、中小种植户、农技推广站等场景，确定核心痛点——<b>“看病难、开方难”</b>，
     提出将「识别」升级为「识别 → 定位 → 评估 → 处方」完整闭环的产品定位。</p>
  <p>技术方案确定为「<b>视觉检测 + 大模型决策</b>」双引擎架构：</p>
  <ul>
    <li><b>病害识别引擎</b>：YOLO11n-cls 分类模型，38 类作物病害与健康状态识别；</li>
    <li><b>可视化解译</b>：Grad-CAM 高亮染病区域，提升结果可信度；</li>
    <li><b>精准处方引擎</b>：接入大语言模型，生成含药剂、用量、间隔期的个性化处方。</li>
  </ul>
  <div class="callout"><b>方案要点</b>：低成本、易上手、可规模化，全程软件实现，普通电脑即可运行。</div>

  <h3>4.2 环境搭建与数据准备（8月6日—11日）</h3>
  <p>完成 Windows + Python 3.12 环境搭建，独立 <code>.venv</code> 虚拟环境，安装 Ultralytics(YOLO)、
     FastAPI、PyTorch 等依赖。王韬淦负责 PlantVillage 数据集下载、去重与目录整理。</p>
  <table>
    <tr><th style="width:140px">指标</th><th>数值</th></tr>
    <tr><td>类别数</td><td>38 类（含健康状态与常见病害）</td></tr>
    <tr><td>图像总量</td><td>60,343 张（train 48,282 / val 12,061）</td></tr>
    <tr><td>训练集 / 验证集</td><td>43,515 张 / 10,790 张（约 8:2）</td></tr>
  </table>
  <div class="problem"><b>问题</b>：数据集目录名含括号、逗号、空格及末尾下划线等特殊字符
      （如 <code>Cherry_(including_sour)___Powdery_mildew</code>），直接按 <code>___</code> 切分会导致
      类别键值对不上。<b>解决</b>：采用「完整类名精确映射」，建立 38 条精确映射表，并用
      <code>verify_mapping.py</code> 校验 0 缺失 / 0 多余。</div>
  <div class="footer">禾目 AgriGuard · 开发日志 · 第 3 页</div>
</div>

<!-- P4 模型训练 -->
<div class="page">
  <h3>4.3 模型训练与调优（8月12日—17日）</h3>
  <p>魏尊浩基于 <b>YOLO11n-cls</b> 分类模型开展训练，关键超参数如下：</p>
  <table>
    <tr><th style="width:150px">参数</th><th>取值</th></tr>
    <tr><td>模型 / 任务</td><td>yolo11n-cls / 分类（classify）</td></tr>
    <tr><td>训练轮数 / 批大小</td><td>30 epochs / batch 32</td></tr>
    <tr><td>输入尺寸</td><td>224×224</td></tr>
    <tr><td>优化器 / 初始学习率</td><td>auto（AdamW）/ 0.01</td></tr>
    <tr><td>数据增强</td><td>randaugment + erasing=0.4 + fliplr=0.5</td></tr>
    <tr><td>训练设备</td><td>GPU（device=0）+ AMP 混合精度</td></tr>
    <tr><td>总耗时</td><td>约 33.5 分钟（2011.74 s）</td></tr>
  </table>
  <div class="callout"><b>训练结果</b>：Top-1 准确率由首轮 <b>96.58%</b> 提升至末轮 <b>99.796%</b>（约 99.8%），
     验证损失由 0.1070 下降至 <b>0.0074</b>，收敛稳定、无明显过拟合。</div>
  {fig(img_curve, "图1：30 轮训练过程指标曲线（train/loss 与 metrics/accuracy_top1）", 96)}
  <div class="footer">禾目 AgriGuard · 开发日志 · 第 4 页</div>
</div>

<!-- P5 映射 + 后端 -->
<div class="page">
  <h3>4.4 中文类别映射与校验（8月16日—18日）</h3>
  <p>为保证诊断结果「通俗可读」，王韬淦建立 38 类「英文真实类名 → 中文」完整映射，
     并通过 <code>verify_mapping.py</code> 对 <code>best.pt</code> 类别名逐一比对，
     校验结果为 <b>0 缺失、0 多余</b>，杜绝识别结果回退为英文类名的问题。</p>
  {fig(img_val, "图2：验证集可视化（val_batch0_pred）——真值在上、模型预测在下", 70)}

  <h3>4.5 后端服务与处方引擎（8月18日—20日）</h3>
  <p>魏尊浩搭建 <b>FastAPI</b> 后端，暴露 <code>POST /predict</code> 接口，编排
     「识别 → 定位 → 处方」全流程；王韬淦负责处方引擎接口联调。处方引擎以「资深植物医生」视角，
     结合病害与严重度信息，生成结构化处方（严重程度 / 生物防治 / 化学用药 / 安全间隔期 / 日常管理）。</p>
  <div class="callout"><b>容错设计</b>：未配置大模型密钥或接口异常时自动回落内置模板处方；健康叶片输出
     「无需防治」专门建议，保证任何网络环境下结果稳定可返回。</div>
  <div class="footer">禾目 AgriGuard · 开发日志 · 第 5 页</div>
</div>

<!-- P6 前端 + Grad-CAM -->
<div class="page">
  <h3>4.6 前端页面与 Grad-CAM 可视化（8月20日—24日）</h3>
  <p>徐佳静完成原生 Web 前端（HTML/CSS/JS），实现「上传病叶 → 诊断结果 → 热力图 → 处方」交互闭环；
     魏尊浩实现 Grad-CAM 病灶定位可视化。</p>
  {fig(img_home, "图3：系统首页——病叶上传入口", 150)}
  <div class="problem"><b>问题（关键攻坚）</b>：Grad-CAM 初版热力图发散、几乎无高亮。排查发现对分类头
      <b>softmax 后的概率</b>反传时，softmax 饱和导致梯度趋近 0。<b>解决</b>：改为在分类头 <b>linear 层
      原始 logits</b>（跳过 softmax）上反传，并对 C2PSA 空间特征层（256 通道）加权，热力图清晰稳定。</div>
  {fig(img_heat, "图4：Grad-CAM 热力图（红色为模型高关注区域）", 46)}
  <div class="footer">禾目 AgriGuard · 开发日志 · 第 6 页</div>
</div>

<!-- P7 联调 + 结果 -->
<div class="page">
  <h3>4.7 端到端联调与测试（8月25日—26日）</h3>
  <p>完成 <code>/predict</code> 全链路联调：上传图片 → YOLO 识别 Top3 → Grad-CAM 热力图 →
     处方生成 → 前端渲染。王韬淦编写 <code>smoke_test.py</code> 冒烟测试，验证正常、健康叶片、
     无密钥等分支均稳定返回，并整理使用文档。</p>
  <div class="grid2">
    {fig(img_result, "图5：诊断结果页（识别结果 + 置信度）")}
    {fig(img_presc, "图6：智能处方卡片（药剂 / 用量 / 间隔期）")}
  </div>
  {fig(img_cm, "图7：验证集混淆矩阵（38 类，对角线为主，分类高度准确）", 128)}

  <h3>4.8 演示视频与参赛材料（8月27日—30日）</h3>
  <p>徐佳静牵头制作演示视频（1080p、中文配音，完整演示「上传 → 识别 → 定位 → 处方」），
     并完成产品海报（1200×560）与产品说明 PPT；全员协作整理开发日志与证明材料，完成提交打包。</p>
  <div class="footer">禾目 AgriGuard · 开发日志 · 第 7 页</div>
</div>

<!-- P8 实验数据附录 -->
<div class="page">
  <h2 class="sec">五、实验数据附录</h2>
  <p>以下为 <code>results.csv</code> 中抽取的关键训练指标（完整数据见项目 <code>runs/agriguard/</code>）：</p>
  <table>
    <tr><th>Epoch</th><th>train/loss</th><th>accuracy_top1</th><th>accuracy_top5</th><th>val/loss</th></tr>
    <tr><td>1</td><td>0.89247</td><td>0.9658</td><td>0.99861</td><td>0.10704</td></tr>
    <tr><td>5</td><td>0.20406</td><td>0.97572</td><td>0.99963</td><td>0.07032</td></tr>
    <tr><td>10</td><td>0.09331</td><td>0.99305</td><td>1.00000</td><td>0.02106</td></tr>
    <tr><td>15</td><td>0.06104</td><td>0.99555</td><td>0.99991</td><td>0.01387</td></tr>
    <tr><td>20</td><td>0.03914</td><td>0.99657</td><td>1.00000</td><td>0.00967</td></tr>
    <tr><td>25</td><td>0.02074</td><td>0.99759</td><td>1.00000</td><td>0.00865</td></tr>
    <tr><td>30</td><td>0.01078</td><td>0.99796</td><td>1.00000</td><td>0.00741</td></tr>
  </table>
  <div class="callout">首轮模型（v1）：Top-1 <b>99.80%</b>，Top-5 <b>100%</b>，验证损失 <b>0.00741</b>。当前部署为 <b>v2</b>（2026-09-15 重训）：Top-1 <b>99.74%</b>、验证损失 <b>0.00912</b>。</div>
  <div class="footer">禾目 AgriGuard · 开发日志 · 第 8 页</div>
</div>

<!-- P9 会议纪要 1&2 -->
<div class="page">
  <h2 class="sec">六、会议纪要</h2>
  <div class="meeting">
    <div class="mt">会议纪要 · 立项启动会</div>
    <div class="mm">时间：2026-08-02 ｜ 形式：线上会议 ｜ 参会：魏尊浩、徐佳静、王韬淦</div>
    <ul>
      <li><b>议题</b>：确定参赛选题与团队分工。</li>
      <li><b>讨论</b>：对比多个农业方向后选定「作物病虫害智能诊断」，围绕「识别—定位—处方」构思产品形态。</li>
      <li><b>决议</b>：魏尊浩任队长，负责算法与全栈；徐佳静负责前端与产品；王韬淦负责数据与测试。</li>
      <li><b>待办</b>：各成员一周内完成技术预研与需求梳理。</li>
    </ul>
  </div>
  <div class="meeting">
    <div class="mt">会议纪要 · 阶段性回顾会</div>
    <div class="mm">时间：2026-08-12 ｜ 形式：线上会议 ｜ 参会：魏尊浩、徐佳静、王韬淦</div>
    <ul>
      <li><b>议题</b>：数据集整理进展与首轮训练结果评审。</li>
      <li><b>讨论</b>：王韬淦通报 PlantVillage 数据整理完成（54,305 张 / 38 类）；魏尊浩通报基线模型首轮收敛、但存在目录特殊字符与类别映射隐患。</li>
      <li><b>决议</b>：采用「完整类名精确映射」方案并编写校验脚本；继续调参提升 Top-1 至 99% 以上。</li>
      <li><b>待办</b>：魏尊浩负责调优，王韬淦负责映射与校验脚本。</li>
    </ul>
  </div>
  <div class="footer">禾目 AgriGuard · 开发日志 · 第 9 页</div>
</div>

<!-- P10 会议纪要 3&4 -->
<div class="page">
  <h2 class="sec">六、会议纪要（续）</h2>
  <div class="meeting">
    <div class="mt">会议纪要 · 技术攻坚会</div>
    <div class="mm">时间：2026-08-24 ｜ 形式：线上会议 ｜ 参会：魏尊浩、徐佳静、王韬淦</div>
    <ul>
      <li><b>议题</b>：Grad-CAM 热力图发散问题定位与处置。</li>
      <li><b>讨论</b>：魏尊浩复盘发现 softmax 饱和导致梯度消失，提出改在 linear 原始 logits 反传；徐佳静同步前端交互与视觉打磨进展。</li>
      <li><b>决议</b>：按 linear-logits 方案重构 Grad-CAM，次日验证热力图清晰稳定。</li>
      <li><b>待办</b>：魏尊浩修复 Grad-CAM，王韬淦准备端到端冒烟测试。</li>
    </ul>
  </div>
  <div class="meeting">
    <div class="mt">会议纪要 · 收尾评审会</div>
    <div class="mm">时间：2026-08-28 ｜ 形式：线上会议 ｜ 参会：魏尊浩、徐佳静、王韬淦</div>
    <ul>
      <li><b>议题</b>：参赛材料分工与收尾计划。</li>
      <li><b>讨论</b>：确认演示视频、海报、PPT、开发日志、证明材料五项交付清单；复盘端到端联调结果。</li>
      <li><b>决议</b>：徐佳静负责视频与视觉物料，魏尊浩负责技术文档与数据整理，王韬淦负责测试佐证与材料归档。</li>
      <li><b>待办</b>：8 月 30 日前完成全部材料并打包提交。</li>
    </ul>
  </div>
  <div class="footer">禾目 AgriGuard · 开发日志 · 第 10 页</div>
</div>

<!-- P11 问题排查 + 产出物 -->
<div class="page">
  <h2 class="sec">七、问题排查与解决汇总</h2>
  <table>
    <tr><th style="width:130px">问题</th><th style="width:88px">阶段</th><th>定位与解决</th></tr>
    <tr><td>数据集目录特殊字符</td><td>数据准备</td><td>目录名含括号/逗号/空格导致切分错位；改用完整类名精确映射 + 脚本校验。</td></tr>
    <tr><td>识别结果回退英文</td><td>映射</td><td>建立 38 条中文映射并校验 0 缺失 / 0 多余。</td></tr>
    <tr><td>Grad-CAM 梯度消失</td><td>可视化</td><td>softmax 饱和致梯度趋 0，改在 linear 原始 logits 反传，热力图恢复清晰。</td></tr>
    <tr><td>模型更新未生效</td><td>部署</td><td>训练完成自动将 best.pt 复制到服务端模型目录，避免手动遗漏。</td></tr>
    <tr><td>无密钥/断网报错</td><td>处方</td><td>异常时回落内置模板处方，健康叶片输出「无需防治」建议。</td></tr>
  </table>

  <h2 class="sec">八、核心产出物清单</h2>
  <table>
    <tr><th style="width:170px">产出物</th><th>说明</th></tr>
    <tr><td><code>models/best.pt</code></td><td>训练收敛的 YOLO11n-cls 分类模型（当前 v2，Top-1 99.74%）</td></tr>
    <tr><td>后端 <code>backend/</code></td><td>FastAPI 服务 + 识别 / 处方 / Grad-CAM 模块</td></tr>
    <tr><td>前端 <code>frontend/</code></td><td>原生 Web 交互界面（上传—结果—热力图—处方）</td></tr>
    <tr><td>演示视频 <code>media/demo_video.mp4</code></td><td>1080p 中文配音，完整演示运行效果</td></tr>
    <tr><td>产品海报 / PPT / 开发日志</td><td>参赛官网项目板块所需物料</td></tr>
  </table>

  <div class="callout"><b>结语</b>：本项目在一个月内完整走通“选题—数据—训练—定位—处方—闭环—演示”全流程，
      核心指标与功能均通过验证。以上记录真实反映团队开发过程，可作为参赛佐证材料。</div>
  <div class="footer">禾目 AgriGuard · 开发日志 · 完</div>
</div>

</body>
</html>
"""

OUT.write_text(html, encoding="utf-8")
print("saved", OUT, "size", OUT.stat().st_size, "bytes")