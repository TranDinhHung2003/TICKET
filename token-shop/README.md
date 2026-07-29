# Facebook Group Poster — Token Shop (Java / Spring Boot)

Website bán token phần mềm **100% Java (Spring Boot 4 + Thymeleaf)**.

## Tính năng

- Shop mua gói token, QR VietQR / chuyển khoản **SePay**
- Webhook SePay tự động xác nhận → cấp token → gửi **Gmail** + lưu **lịch sử mua hàng**
- Đăng ký email + **OTP**, đăng nhập form, đăng nhập nhanh **Google**
- Admin: log mua bán (người mua → thời hạn), đơn hàng, bảng giá, token, tài khoản
- API desktop: `POST /api/v1/activate`, `POST /api/v1/verify`

## Chạy nhanh

```bash
cd token-shop
./mvnw spring-boot:run
```

Mở http://localhost:8080

Admin mặc định: `admin@local.test` / `Admin@123456` (đổi bằng env).

## Cấu hình

Xem `.env.example`.

### SePay

1. Tạo webhook trỏ tới `{APP_BASE_URL}/api/sepay/webhook`
2. Auth: `Authorization: Apikey {SEPAY_API_KEY}`
3. Điền `SEPAY_BANK`, `SEPAY_ACCOUNT`, `SEPAY_ACCOUNT_NAME`, `SEPAY_API_KEY`

Khi nhận tiền vào, SePay POST JSON; shop khớp mã `FBPAY...` trong nội dung CK, kiểm tra số tiền ≥ đơn, rồi cấp token.

### Gmail OTP / giao token

Bật 2FA Gmail → App Password → `MAIL_USERNAME` / `MAIL_PASSWORD`.

### Google login

Google Cloud OAuth client, redirect:

`{APP_BASE_URL}/login/oauth2/code/google`

Set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.

### App desktop

Trong license config trỏ server về shop Java, ví dụ:

`http://localhost:8080`

(endpoints `/api/v1/activate` và `/api/v1/verify`).

## Build

```bash
./mvnw -DskipTests package
java -jar target/token-shop-0.0.1-SNAPSHOT.jar
```
