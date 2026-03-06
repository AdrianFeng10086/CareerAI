# Boss 直聘扫码登录流程分析 (修正版)

本文档根据对网络请求的精确分析，详细记录了 Boss 直聘 PC 网页端扫码登录的完整技术流程。特别感谢用户的指正，修正了初版分析中的错误。

## 核心流程

整个登录过程分为几个明确的步骤，涉及多个 API 端点，并通过长轮询（Long Polling）来同步客户端与服务器的状态。

### 1. 获取登录会话信息

登录流程的起点是获取一次性会话所需的关键信息，包括二维码 ID 和加密密钥。

- **API:** `POST https://www.zhipin.com/wapi/zppassport/captcha/randkey`
- **作用:** 此请求是登录流程的初始化步骤。
- **返回内容:** 服务器返回一个 JSON 对象，包含本次登录会话所需的所有关键信息：
  ```json
  {
      "code": 0,
      "message": "Success",
      "zpData": {
          "qrId": "bosszp-9b0b83cf-f878-4c19-8fcb-d7e7e8d99a40",
          "randKey": "vePY0x8IZpBVQ0wH8gvPMQ7pqXJT5y0e",
          "secretKey": "VNlUWtkz",
          "shortRandKey": "bosszp-kq7bwZNGg41rVI14"
      }
  }
  ```

### 2. 获取二维码图片

使用上一步获取的 `qrId` 来生成可供手机 APP 扫描的二维码。

- **API:** `GET https://www.zhipin.com/wapi/zpweixin/qrcode/getqrcode`
- **参数:**
    - `content`: 上一步返回的 `qrId`。
- **作用:** 生成二维码图片。

### 3. 检查扫码状态（长轮询）

二维码生成后，浏览器启动一个长轮询来等待用户扫码。

- **API:** `GET https://www.zhipin.com/wapi/zppassport/qrcode/scan`
- **参数:**
    - `uuid`: 此处传入的是第一步获取的 `qrId`。
- **作用:** 这是一个阻塞请求。服务器会保持连接，直到用户扫码或请求超时。
    - **扫码成功:** 请求返回 200 OK，并告知浏览器用户已扫码。
    - **超时:** 请求返回 `{"msg":"timeout","scaned":false}`。

### 4. 检查登录确认状态（长轮询）

用户扫码后，浏览器会立即启动另一个长轮询，等待用户在手机上点击“确认登录”按钮。

- **API:** `GET https://www.zhipin.com/wapi/zppassport/qrcode/scanLogin`
- **参数:**
    - `qrId`: 第一步获取的 `qrId`。
- **作用:** 这同样是一个阻塞请求。服务器保持连接，直到用户在手机上确认登录。
    - **确认成功:** 请求返回 200 OK。

### 5. 获取最终 Cookie

用户确认登录后，浏览器发起最后一步请求，以获取包含最终登录凭证的 Cookie。

- **API:** `GET https://www.zhipin.com/wapi/zppassport/qrcode/dispatcher`
- **参数:**
    - `qrId`: 第一步获取的 `qrId`。
    - `pk`: 通常是固定的值，如 `header-login`。
    - `fp`: 一个经过编码或加密的设备指纹（Fingerprint）参数。
- **作用:** 这是完成登录的最后一步。服务器验证所有参数后，会在这个请求的响应头中通过 `Set-Cookie` 设置登录凭证。

## `fp` 参数生成算法解析

`fp` 参数是设备指纹（Fingerprint）的缩写，其生成算法基于 AES 加密，目的是增加登录请求的唯一性和安全性。

### 核心JS代码

```javascript
function ne() {
    var t, e, n = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : "", r = arguments.length > 1 && void 0 !== arguments[1] ? arguments[1] : "";
    if (!r || !n)
        return "";
    n = Xt().parse(n);
    var o = Xt().parse(r)
      , i = ee().random(16)
      , a = Jt().encrypt(n, o, {
        iv: i
    })
      , c = k()(t = k()(e = ee().create()).call(e, i)).call(t, a.ciphertext);
    return Yt().stringify(c)
}
```

### 算法步骤

1.  **准备密钥 (Key)**: 将一个固定的 Base64 字符串 (例如 `clRwXUJBK1VKK0k0IWFbbQ==`) 解码，得到的结果 (例如 `rTp]BA+UJ+I4!a[m`) 作为 AES 加密的密钥。

2.  **准备明文 (Plaintext)**: 一个由多个部分组成的、用点号连接的长字符串 (例如 `8048b...bd95`) 作为需要加密的原始数据。

3.  **生成随机IV**: `ee().random(16)` 会生成一个16字节的随机数据，作为 AES 加密的初始化向量 (IV)。

4.  **AES/CBC 加密**: 使用步骤1的密钥和步骤3的随机 IV，通过 AES 的 CBC (Cipher Block Chaining) 模式对明文进行加密。

5.  **组合结果**: 将随机生成的 IV 和加密后的密文 (`ciphertext`) 拼接在一起。

6.  **Base64 编码**: 对拼接后的数据 (IV + Ciphertext) 进行 Base64 编码，得到最终的 `fp` 字符串。

### Python 实现

以下 Python 代码使用 `pycryptodome` 库完整复现了 `fp` 的生成过程。

```python
# -*- coding: utf-8 -*-
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Random import get_random_bytes

def generate_fp(i_str, e_b64):
    """
    生成 Boss 直聘登录所需的 fp 设备指纹参数。

    :param i_str: 明文字符串 (e.g., "8048b...bd95")
    :param e_b64: 作为密钥的 Base64 字符串 (e.g., "clRwXUJBK1VKK0k0IWFbbQ==")
    :return: Base64 编码后的 fp 字符串
    """
    # 1. 准备密钥和明文
    key_bytes = base64.b64decode(e_b64)
    plaintext_bytes = i_str.encode('utf-8')

    # 2. 生成一个16字节的随机IV
    iv_bytes = get_random_bytes(16)

    # 3. 使用AES/CBC模式进行加密 (需要对明文进行PKCS7填充)
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
    padded_plaintext = pad(plaintext_bytes, AES.block_size)
    ciphertext_bytes = cipher.encrypt(padded_plaintext)

    # 4. 组合 IV 和密文
    result_bytes = iv_bytes + ciphertext_bytes

    # 5. 进行Base64编码得到最终的fp值
    fp = base64.b64encode(result_bytes).decode('utf-8')
    return fp

# --- 示例调用 ---
if __name__ == "__main__":
    # 实际值需要从页面JS或网络请求中动态获取
    i_input = "8048b8676fb7d3d8952276e6e98e0bde.f2dc7a63c4b0fbfa4b51a07e2710cf83.fef7e750fc3a1e6327e8a880915aee9c.ae00f848beb1aa591d71d5a80dd3bd95"
    E_input = "clRwXUJBK1VKK0k0IWFbbQ=="

    generated_fp = generate_fp(i_input, E_input)
    print(f"Generated fp (will be different each time): {generated_fp}")
```
