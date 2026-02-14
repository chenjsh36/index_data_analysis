# GitHub 仓库配置说明（v6）

在浏览器中打开仓库：**https://github.com/chenjsh36/index_data_analysis**，按下列步骤操作。

---

## 1. 启用 Actions

1. 进入仓库顶部 **Actions** 标签。
2. 若首次使用，点击 **I understand my workflows, go ahead and enable them** 启用工作流。
3. 左侧会看到工作流 **「每日信号」**（来自 `.github/workflows/daily_signal.yml`）。

---

## 2. 配置 Secrets（推送渠道）

进入 **Settings** → **Secrets and variables** → **Actions**，点击 **New repository secret** 添加以下项。

### 邮件推送（可选，三选一或都配）

| Secret 名称 | 说明 | 示例 |
|-------------|------|------|
| `EMAIL_SENDER` | 发件人邮箱 | `your@qq.com` |
| `EMAIL_PASSWORD` | 邮箱授权码（非登录密码，在邮箱设置里开 SMTP 并生成） | 授权码字符串 |
| `EMAIL_RECEIVERS` | 收件人，多个用英文逗号分隔；留空则发到发件人自己 | `a@x.com,b@y.com` |

### 钉钉推送（可选）

| Secret 名称 | 说明 |
|-------------|------|
| `CUSTOM_WEBHOOK_URLS` | 钉钉机器人 Webhook 地址；多个用英文逗号分隔。在钉钉群 → 群设置 → 智能群助手 → 添加机器人 → 自定义，复制 Webhook URL。 |

### 可选：标的与策略

| Secret 名称 | 说明 | 默认 |
|-------------|------|------|
| `SYMBOL` | 标的代码 | 不设则为 `QQQ` |
| `STRATEGY` | 策略名 | 不设则为 `EMA_trend_v2` |

**说明**：至少配置**一种**推送方式（邮件或钉钉），否则工作流会正常跑信号但不会发送通知。

---

## 3. 手动运行一次

1. 打开 **Actions** → 左侧点击 **每日信号**。
2. 右侧 **Run workflow** → 选择分支 `main` → 点击 **Run workflow**。
3. 运行完成后在列表里点进该次运行，可查看日志；若已配置 Secrets，应收到邮件或钉钉消息。

---

## 4. 定时说明

- 工作流已配置 **每日 UTC 22:00**（约北京时间次日 06:00）自动运行。
- 若需改时间，可编辑 `.github/workflows/daily_signal.yml` 中的 `schedule` 的 cron 表达式，提交后生效。

---

## 5. 静态页部署（可选）

若希望通过 GitHub Pages 公网访问「5 年走势 + 当日信号」页面：

- GitHub 仅支持从 **根目录** 或 **/docs** 发布。当前页面在 `web/` 下，可选做法：
  1. **Settings** → **Pages** → Source 选 **Deploy from a branch**，Branch 选 `main`，Folder 选 **/docs**；在仓库中把 `web/` 下的 `index.html`、`timeseries.json`、`signal.json` 复制到 `docs/`（或建 `docs/dashboard/` 放进去），并确保 `index.html` 里请求的 JSON 路径与发布后 URL 一致。
  2. 或使用 **GitHub Actions** 做静态站发布（需另写 workflow 把 `web/` 推到 `gh-pages` 等）。
- 当前未在 CI 中自动生成 JSON，Pages 上显示的是你上次提交的静态文件；若需每日更新，可后续在「每日信号」workflow 里增加生成 JSON 并提交/发布的步骤。

---

配置完成后，每日会自动跑一次信号并按你的 Secrets 推送；需要时也可在 Actions 里手动运行「每日信号」。
