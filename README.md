# Xe Ghép & Taxi Thùy Nguyễn — Website Đặt Xe Ghép Miền Bắc

Website tĩnh (HTML/CSS/JavaScript thuần, không cần build) cho dịch vụ **xe ghép** và **taxi / bao xe đường dài** khu vực miền Bắc, gồm giao diện khách hàng chuẩn SEO và bảng quản trị.

Tuyến phục vụ: Hà Nội – Hải Phòng, Hà Nội – Hạ Long, Hà Nội – Ninh Bình, Hà Nội – Sapa và taxi sân bay Nội Bài.

## Cấu trúc hệ thống

### Giao diện khách hàng (Public)

| Trang | Tệp | Nội dung |
|---|---|---|
| Trang chủ | `index.html` | Thanh tìm chuyến (điểm đi/đến, ngày, loại dịch vụ), ưu điểm, tuyến xe ghép phổ biến kèm bảng giá, đánh giá khách hàng |
| Đặt xe | `booking.html` | 4 bước: chọn dịch vụ (xe ghép theo ghế / bao xe riêng) & tuyến → chọn khung giờ hoặc giờ đón → chọn ghế trên sơ đồ xe 7 chỗ hoặc chọn loại xe 4–16 chỗ → địa chỉ đón tận nhà & thanh toán |
| Về chúng tôi | `about.html` | Giới thiệu, chặng đường phát triển, đội xe (sedan 4 chỗ, MPV 7 chỗ, limousine 9–16 chỗ), cam kết chất lượng |
| Blog / Tin tức | `blog.html` | Cẩm nang du lịch miền Bắc, kinh nghiệm đi xe ghép, thông tin tuyến đường (chuẩn SEO) |
| Liên hệ | `contact.html` | Hotline 24/7, văn phòng Hà Nội / Hải Phòng / Sapa, bản đồ Google Maps, biểu mẫu gửi ý kiến |

### Bảng quản trị (Admin)

| Trang | Tệp | Nội dung |
|---|---|---|
| Dashboard | `admin/index.html` | Thống kê doanh thu, ghế ghép + cuốc bao xe đã bán, tỷ lệ lấp đầy theo tuyến, lịch xe trong ngày |
| Quản lý chuyến xe | `admin/trips.html` | Thêm / sửa / xóa chuyến ghép và cuốc bao xe, cập nhật giá vé, giờ chạy, tìm kiếm & lọc |
| Quản lý đặt xe | `admin/bookings.html` | Duyệt đơn, xác nhận thanh toán, hủy chuyến, lọc theo trạng thái |
| Quản lý SEO | `admin/seo.html` | Cấu hình Meta Title, Meta Description, Schema Markup (JSON-LD), từ khóa cho từng trang; xem trước kết quả Google |

## Chuẩn SEO đã áp dụng

- Thẻ meta đầy đủ: `title`, `description`, `keywords`, `robots`, `canonical`
- Open Graph (`og:*`) và Twitter Card cho chia sẻ mạng xã hội
- Schema Markup JSON-LD: `TaxiService`, `LocalBusiness`, `AboutPage`, `Blog`, `ContactPage`, `AggregateRating`
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

Trang quản trị: `http://localhost:8000/admin/` (bản demo chưa gắn xác thực; dữ liệu chuyến xe / đơn đặt là dữ liệu minh hoạ trong bộ nhớ trang, cấu hình SEO lưu vào `localStorage`).

## Ghi chú kỹ thuật

- Không phụ thuộc framework hay thư viện ngoài (chỉ dùng Google Fonts).
- `js/booking.js` nhận tham số URL (`?route=hn-hp` hoặc `?from=hn&to=hp&service=ghep&date=...`) để điền sẵn tuyến và loại dịch vụ từ trang chủ.
- Khi triển khai thực tế, thay các thao tác trong `admin/js/*.js` và form đặt xe bằng lời gọi API backend.
