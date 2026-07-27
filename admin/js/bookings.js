/* Quản lý đặt vé — duyệt vé, xác nhận thanh toán, hủy vé (dữ liệu minh hoạ) */

var bookings = [
  { code: "TN26072701", name: "Nguyễn Lan Phương", phone: "0912345678", route: "Sài Gòn → Đà Lạt", time: "06:00", seats: "A03, A04", total: 580000, pay: "Chuyển khoản", status: "pending" },
  { code: "TN26072702", name: "Trần Minh Tuấn", phone: "0987654321", route: "Sài Gòn → Nha Trang", time: "11:00", seats: "B05", total: 320000, pay: "MoMo", status: "paid" },
  { code: "TN26072703", name: "Lê Thu Hà", phone: "0909112233", route: "Sài Gòn → Cần Thơ", time: "16:00", seats: "C01, C02", total: 360000, pay: "Tiền mặt", status: "approved" },
  { code: "TN26072704", name: "Phạm Quốc Bảo", phone: "0933445566", route: "Đà Lạt → Sài Gòn", time: "20:00", seats: "A01", total: 290000, pay: "ZaloPay", status: "pending" },
  { code: "TN26072705", name: "Võ Thị Kim Chi", phone: "0977889900", route: "Sài Gòn → Mũi Né", time: "13:30", seats: "B02, B03, B04", total: 660000, pay: "Chuyển khoản", status: "paid" },
  { code: "TN26072706", name: "Đặng Văn Hùng", phone: "0966123123", route: "Nha Trang → Sài Gòn", time: "22:30", seats: "C07", total: 320000, pay: "Tiền mặt", status: "cancelled" },
  { code: "TN26072707", name: "Hoàng Mỹ Duyên", phone: "0944556677", route: "Sài Gòn → Đà Lạt", time: "08:30", seats: "A05, A06", total: 580000, pay: "MoMo", status: "pending" }
];

var STATUS_LABEL = {
  pending: "<span class='badge amber'>Chờ duyệt</span>",
  approved: "<span class='badge blue'>Đã duyệt</span>",
  paid: "<span class='badge green'>Đã thanh toán</span>",
  cancelled: "<span class='badge red'>Đã hủy</span>"
};

document.addEventListener("DOMContentLoaded", function () {
  renderBookings();
  document.getElementById("bk-search").addEventListener("input", renderBookings);
  document.getElementById("bk-filter-status").addEventListener("change", renderBookings);
});

function renderBookings() {
  var query = document.getElementById("bk-search").value.toLowerCase();
  var status = document.getElementById("bk-filter-status").value;
  var tbody = document.getElementById("bookings-body");
  tbody.innerHTML = "";

  var visible = bookings.filter(function (b) {
    var matchText = (b.code + " " + b.name + " " + b.phone + " " + b.route).toLowerCase().indexOf(query) >= 0;
    var matchStatus = status === "all" || b.status === status;
    return matchText && matchStatus;
  });

  visible.forEach(function (b) {
    var actions = "";
    if (b.status === "pending") {
      actions =
        "<button class='btn btn-primary btn-sm' onclick=\"approveBooking('" + b.code + "')\">✓ Duyệt vé</button>" +
        "<button class='btn btn-danger btn-sm' onclick=\"cancelBooking('" + b.code + "')\">✕ Hủy</button>";
    } else if (b.status === "approved") {
      actions =
        "<button class='btn btn-success btn-sm' onclick=\"confirmPayment('" + b.code + "')\">💰 Xác nhận TT</button>" +
        "<button class='btn btn-danger btn-sm' onclick=\"cancelBooking('" + b.code + "')\">✕ Hủy</button>";
    } else if (b.status === "paid") {
      actions = "<button class='btn btn-danger btn-sm' onclick=\"cancelBooking('" + b.code + "')\">✕ Hủy</button>";
    } else {
      actions = "<span style='color:#94a3b8;font-size:13px'>—</span>";
    }

    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td><strong>" + b.code + "</strong></td>" +
      "<td>" + b.name + "<br><small style='color:#64748b'>" + b.phone + "</small></td>" +
      "<td>" + b.route + "<br><small style='color:#64748b'>" + b.time + " • Ghế " + b.seats + "</small></td>" +
      "<td class='money'>" + formatVND(b.total) + "</td>" +
      "<td>" + b.pay + "</td>" +
      "<td>" + STATUS_LABEL[b.status] + "</td>" +
      "<td><div class='actions'>" + actions + "</div></td>";
    tbody.appendChild(tr);
  });

  updateCounters();
}

function updateCounters() {
  var counts = { pending: 0, approved: 0, paid: 0, cancelled: 0 };
  bookings.forEach(function (b) { counts[b.status]++; });
  document.getElementById("cnt-pending").textContent = counts.pending;
  document.getElementById("cnt-approved").textContent = counts.approved;
  document.getElementById("cnt-paid").textContent = counts.paid;
  document.getElementById("cnt-cancelled").textContent = counts.cancelled;
}

function findBooking(code) {
  return bookings.find(function (b) { return b.code === code; });
}

function approveBooking(code) {
  var b = findBooking(code);
  if (!b) return;
  b.status = "approved";
  renderBookings();
  showToast("✓ Đã duyệt vé " + code + " — chờ xác nhận thanh toán");
}

function confirmPayment(code) {
  var b = findBooking(code);
  if (!b) return;
  b.status = "paid";
  renderBookings();
  showToast("💰 Đã xác nhận thanh toán " + formatVND(b.total) + " cho vé " + code);
}

function cancelBooking(code) {
  var b = findBooking(code);
  if (!b) return;
  if (confirm("Hủy vé " + code + " của khách " + b.name + "?\nGhế sẽ được mở bán lại.")) {
    b.status = "cancelled";
    renderBookings();
    showToast("Đã hủy vé " + code);
  }
}
