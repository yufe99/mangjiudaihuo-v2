# 商业模式(预留)

## 三种收入路径

| 模式 | 用户 | 平台收入 | 架构支持 |
|---|---|---|---|
| **BYOK** | 自带 toapis/yijia/302 key | 0(引流) | ✅ `billing_mode="byok"` + provider_configs |
| **平台积分** | 充值买 credits | API 差价 + 抽成 | ✅ `billing_mode="credit"` + User.credits |
| **订阅 / Token** | 月/年费 | 稳定 MRR | 🔜 预留(User.plan 字段) |

## 积分计价草案(待定)

- 1 积分 = 1 次标准调用
- 剧本生成: 5 积分
- 单张角色图: 10 积分
- 单条视频: 50 积分
- TTS: 2 积分/条
- 合成: 5 积分/集

## 实现顺序

1. ✅ BYOK(用户填 key,直接调)
2. 🔜 Credit 计费(拦截 provider 调用 → 扣积分 → 调平台 key)
3. 🔜 订阅(Stripe / Creem / PayPal 接入,跟 bodyscore 同款双通道)
4. 🔜 Token 卖断(高级功能解锁)