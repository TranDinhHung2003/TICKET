# Facebook Group Poster — Token Shop (Java / Spring Boot)

Website bán token **100% Java (Spring Boot 4 + Thymeleaf)**.

## Chạy nhanh (không cần gõ CMD)

**Windows (khuyến nghị):** double-click

- `start_token_shop.bat` (ở thư mục gốc repo) — chạy ẩn, tự mở trình duyệt
- hoặc `token-shop/start_shop_silent.vbs`
- hoặc `token-shop/start_shop.bat` (có cửa sổ log)

**Linux/macOS:**

```bash
chmod +x token-shop/start_shop.sh
./token-shop/start_shop.sh
```

Mở http://localhost:8080

Admin mặc định: `admin@local.test` / `Admin@123456`

## Tính năng bán hàng tự động

- Khách chọn **thời hạn gói** trên web
- Chuyển khoản **MB Bank** STK `0910108069999` (VietQR / SePay)
- Webhook SePay → **tự tạo token đúng thời hạn gói** → gửi **Gmail** + lưu lịch sử
- Thời hạn token **bắt đầu khi khách kích hoạt** trên máy (đúng gói đã mua)
- Admin: log mua bán, bảng giá, token, tài khoản
- API desktop: `POST /api/v1/activate`, `POST /api/v1/verify`

## Cấu hình

Xem `.env.example`.

### SePay + MB Bank

1. Webhook: `{APP_BASE_URL}/api/sepay/webhook`
2. Auth: `Authorization: Apikey {SEPAY_API_KEY}`
3. Mặc định:
   - `SEPAY_BANK=MB`
   - `SEPAY_ACCOUNT=0910108069999`
   - `SEPAY_ACCOUNT_NAME=MB BANK` (đổi tên chủ TK thật)

### Gmail / Google login

Xem `.env.example`.

### App desktop (khách chạy tool)

License server mặc định: `http://127.0.0.1:8080`  
(`activate` / `verify`).

## Build JAR (để start_shop.bat chạy nhanh hơn)

```bash
cd token-shop
./mvnw -DskipTests package
```

Sau đó `start_shop.bat` sẽ ưu tiên chạy file JAR trong `target/`.
