# Nhà Xe Thùy Nguyễn — Website Đặt Vé Xe Khách

Website tĩnh (HTML/CSS/JavaScript thuần, không cần build) cho nhà xe Thùy Nguyễn, gồm giao diện khách hàng chuẩn SEO và bảng quản trị.

## Cấu trúc hệ thống

### Giao diện khách hàng (Public)

| Trang | Tệp | Nội dung |
|---|---|---|
| Trang chủ | `index.html` | Thanh tìm kiếm chuyến đi, ưu điểm nhà xe, tuyến phổ biến, đánh giá khách hàng |
| Đặt vé / Lịch trình | `booking.html` | Chọn tuyến, chọn giờ, chọn vị trí ghế, điền thông tin và thanh toán (4 bước) |
| Về chúng tôi | `about.html` | Giới thiệu nhà xe, chặng đường phát triển, đội xe, cam kết chất lượng |
| Blog / Tin tức | `blog.html` | Cẩm nang du lịch, kinh nghiệm đi xe, thông tin tuyến đường (chuẩn SEO) |
| Liên hệ | `contact.html` | Hotline, địa chỉ văn phòng, bản đồ Google Maps, biểu mẫu gửi ý kiến |

### Bảng quản trị (Admin)

| Trang | Tệp | Nội dung |
|---|---|---|
| Dashboard | `admin/index.html` | Thống kê doanh thu, số vé đã đặt, tỷ lệ lấp đầy, lịch trình trong ngày |
| Quản lý chuyến xe | `admin/trips.html` | Thêm / sửa / xóa chuyến, cập nhật giá vé, giờ chạy, tìm kiếm & lọc |
| Quản lý đặt vé | `admin/bookings.html` | Duyệt vé, xác nhận thanh toán, hủy vé, lọc theo trạng thái |
| Quản lý SEO | `admin/seo.html` | Cấu hình Meta Title, Meta Description, Schema Markup (JSON-LD), từ khóa cho từng trang; xem trước kết quả Google |

## Chuẩn SEO đã áp dụng

- Thẻ meta đầy đủ: `title`, `description`, `keywords`, `robots`, `canonical`
- Open Graph (`og:*`) và Twitter Card cho chia sẻ mạng xã hội
- Schema Markup JSON-LD: `BusCompany`, `AboutPage`, `Blog`, `ContactPage`, `AggregateRating`
- HTML ngữ nghĩa: `header`, `nav`, `main`, `section`, `article`, `footer`, breadcrumb, thuộc tính ARIA
- `robots.txt` (chặn index thư mục `/admin/`) và `sitemap.xml`
- Trang quản trị gắn `noindex, nofollow`
- Giao diện responsive, tối ưu di động (menu hamburger, nút gọi nhanh)

## Chạy thử

Không cần cài đặt gì, chỉ cần một web server tĩnh:

```bash
python3 -m http.server 8000
# rồi mở http://localhost:8000
```

Trang quản trị: `http://localhost:8000/admin/` (bản demo chưa gắn xác thực; dữ liệu chuyến xe / vé là dữ liệu minh hoạ trong bộ nhớ trang, cấu hình SEO lưu vào `localStorage`).

## Ghi chú kỹ thuật

- Không phụ thuộc framework hay thư viện ngoài (chỉ dùng Google Fonts).
- `js/booking.js` nhận tham số URL (`?route=sg-dl` hoặc `?from=sg&to=dl&date=...`) để điền sẵn tuyến từ trang chủ.
- Khi triển khai thực tế, thay các thao tác trong `admin/js/*.js` và form đặt vé bằng lời gọi API backend.
