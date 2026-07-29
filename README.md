# Facebook Group Poster

Tool Python để đăng bài quảng cáo lên nhiều nhóm Facebook cùng lúc thông qua Facebook Graph API.

## Tính năng

- Liệt kê tất cả nhóm mà tài khoản đang tham gia
- Đăng bài văn bản, có link, hoặc có ảnh vào nhiều nhóm
- Hỗ trợ chạy nhiều chiến dịch từ một file JSON (batch mode)
- Tự động retry khi bị rate limit
- Delay có thể cấu hình giữa các lần đăng
- Báo cáo kết quả chi tiết (JSON)
- Chế độ `--dry-run` để kiểm tra trước khi đăng thật

## Cài đặt

```bash
pip install -e .
```

hoặc cài trực tiếp từ requirements:

```bash
pip install -r requirements.txt
```

## Cấu hình

Sao chép file `.env.example` thành `.env` và điền access token:

```bash
cp .env.example .env
```

Nội dung `.env`:

```
FB_ACCESS_TOKEN=your_facebook_access_token_here
```

### Lấy Access Token

1. Truy cập [Facebook Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Chọn ứng dụng của bạn (hoặc tạo mới tại [developers.facebook.com](https://developers.facebook.com))
3. Cấp quyền cần thiết:
   - `publish_to_groups` — để đăng bài lên nhóm
   - `groups_access_member_info` — để lấy danh sách nhóm
4. Click **Generate Access Token** và sao chép token

> **Lưu ý:** User Access Token mặc định hết hạn sau ~1–2 giờ.  
> Để chạy tự động lâu dài, hãy tạo **Long-Lived Token** hoặc dùng **System User Token** từ Business Manager.

## Sử dụng

### 1. Liệt kê nhóm và lưu ra file

```bash
fb-poster list-groups --save groups.json
```

Kết quả hiển thị bảng và lưu danh sách nhóm JSON vào `groups.json`.

### 2. Đăng bài văn bản

```bash
fb-poster post --message "Nội dung quảng cáo ở đây" --groups-file groups.json
```

### 3. Đăng bài có link

```bash
fb-poster post \
  --message "Xem ngay sản phẩm mới!" \
  --link "https://example.com/san-pham" \
  --groups-file groups.json
```

### 4. Đăng bài có ảnh (file cục bộ)

```bash
fb-poster post \
  --message "Khuyến mãi hôm nay!" \
  --image banner.jpg \
  --groups-file groups.json
```

### 5. Đăng bài có ảnh (URL)

```bash
fb-poster post \
  --message "Khuyến mãi hôm nay!" \
  --image-url "https://example.com/banner.jpg" \
  --groups-file groups.json
```

### 6. Đăng vào nhóm cụ thể

```bash
fb-poster post \
  --message "Quảng cáo test" \
  --group-ids "123456789,987654321,111222333"
```

### 7. Chạy thử (không đăng thật)

```bash
fb-poster post --message "Test" --groups-file groups.json --dry-run
```

### 8. Lưu báo cáo kết quả

```bash
fb-poster post \
  --message "Nội dung" \
  --groups-file groups.json \
  --report report.json
```

### 9. Đăng nhiều chiến dịch (batch mode)

```bash
fb-poster post-batch examples/campaign.json
```

Xem file `examples/campaign.json` để hiểu cấu trúc.

## Tùy chọn toàn cục

| Tùy chọn | Mô tả |
|-----------|-------|
| `--token TOKEN` | Facebook Access Token (hoặc đặt trong `.env`) |
| `--delay SECONDS` | Thời gian chờ giữa các bài đăng (mặc định: 15s) |
| `--skip-ids ID1,ID2` | Bỏ qua nhóm theo ID |
| `--dry-run` | Chạy thử, không đăng thật |
| `--report FILE` | Lưu báo cáo JSON |
| `-v / --verbose` | Hiển thị log chi tiết |

## Cấu trúc file campaign JSON

```json
[
  {
    "message": "Nội dung bài đăng",
    "link": "https://example.com",
    "image_url": "https://example.com/img.jpg",
    "image_path": "/đường/dẫn/ảnh.jpg",
    "delay": 15,
    "groups": [
      {"id": "123456789", "name": "Tên nhóm"},
      {"id": "987654321", "name": "Nhóm khác"}
    ]
  }
]
```

## Lưu ý quan trọng

- **Không spam:** Đăng quá nhiều bài trong thời gian ngắn có thể dẫn đến tài khoản bị hạn chế hoặc khóa. Hãy đặt `--delay` hợp lý (tối thiểu 15–30 giây).
- **Quy định nhóm:** Hãy đọc và tuân thủ nội quy của từng nhóm trước khi đăng bài quảng cáo.
- **Chính sách Facebook:** Sử dụng tool này phù hợp với [Điều khoản dịch vụ của Facebook](https://www.facebook.com/terms.php) và [Chính sách nền tảng](https://developers.facebook.com/policy/).

## Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Giải pháp |
|-----|-------------|-----------|
| `OAuthException code=200` | Token thiếu quyền | Thêm quyền `publish_to_groups` |
| `OAuthException code=190` | Token hết hạn | Lấy token mới |
| `Rate limit` | Đăng quá nhiều | Tăng `--delay`, chờ vài giờ |
| `(#200) Permissions error` | Nhóm không cho phép đăng | Bỏ qua nhóm đó |
