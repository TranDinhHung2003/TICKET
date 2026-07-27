/* Quản lý chuyến xe — thêm / sửa / xóa (dữ liệu minh hoạ, lưu trong bộ nhớ trang) */

var trips = [
  { id: 1, route: "Sài Gòn → Đà Lạt", time: "06:00", bus: "Limousine 21 giường", plate: "51B-123.45", price: 290000, seats: 21, status: "active" },
  { id: 2, route: "Sài Gòn → Đà Lạt", time: "08:30", bus: "Limousine 21 giường", plate: "51B-234.56", price: 290000, seats: 21, status: "active" },
  { id: 3, route: "Sài Gòn → Nha Trang", time: "11:00", bus: "Giường nằm 34 chỗ", plate: "51B-345.67", price: 320000, seats: 34, status: "active" },
  { id: 4, route: "Sài Gòn → Mũi Né", time: "13:30", bus: "Limousine 21 giường", plate: "51B-456.78", price: 220000, seats: 21, status: "paused" },
  { id: 5, route: "Sài Gòn → Cần Thơ", time: "16:00", bus: "Giường nằm 34 chỗ", plate: "51B-567.89", price: 180000, seats: 34, status: "active" },
  { id: 6, route: "Đà Lạt → Sài Gòn", time: "20:00", bus: "Limousine 21 giường", plate: "49B-678.90", price: 290000, seats: 21, status: "active" },
  { id: 7, route: "Nha Trang → Sài Gòn", time: "22:30", bus: "Giường nằm 34 chỗ", plate: "79B-789.01", price: 320000, seats: 34, status: "active" }
];
var nextId = 8;
var editingId = null;

document.addEventListener("DOMContentLoaded", function () {
  renderTrips();
  document.getElementById("trip-search").addEventListener("input", renderTrips);
  document.getElementById("trip-filter-status").addEventListener("change", renderTrips);
});

function renderTrips() {
  var query = document.getElementById("trip-search").value.toLowerCase();
  var status = document.getElementById("trip-filter-status").value;
  var tbody = document.getElementById("trips-body");
  tbody.innerHTML = "";

  trips
    .filter(function (t) {
      var matchText = (t.route + " " + t.plate + " " + t.bus).toLowerCase().indexOf(query) >= 0;
      var matchStatus = status === "all" || t.status === status;
      return matchText && matchStatus;
    })
    .forEach(function (t) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td><strong>" + t.route + "</strong><br><small style='color:#64748b'>" + t.bus + "</small></td>" +
        "<td>" + t.time + "</td>" +
        "<td>" + t.plate + "</td>" +
        "<td>" + t.seats + "</td>" +
        "<td class='money'>" + formatVND(t.price) + "</td>" +
        "<td>" + (t.status === "active"
          ? "<span class='badge green'>Đang chạy</span>"
          : "<span class='badge gray'>Tạm dừng</span>") + "</td>" +
        "<td><div class='actions'>" +
          "<button class='btn btn-ghost btn-sm' onclick='editTrip(" + t.id + ")'>✏️ Sửa</button>" +
          "<button class='btn btn-danger btn-sm' onclick='deleteTrip(" + t.id + ")'>🗑 Xóa</button>" +
        "</div></td>";
      tbody.appendChild(tr);
    });

  document.getElementById("trip-count").textContent = trips.length + " chuyến";
}

function openTripModal() {
  editingId = null;
  document.getElementById("trip-modal-title").textContent = "Thêm chuyến xe mới";
  document.getElementById("trip-form").reset();
  openModal("trip-modal");
}

function editTrip(id) {
  var t = trips.find(function (x) { return x.id === id; });
  if (!t) return;
  editingId = id;
  document.getElementById("trip-modal-title").textContent = "Cập nhật chuyến xe";
  document.getElementById("t-route").value = t.route;
  document.getElementById("t-time").value = t.time;
  document.getElementById("t-bus").value = t.bus;
  document.getElementById("t-plate").value = t.plate;
  document.getElementById("t-price").value = t.price;
  document.getElementById("t-seats").value = t.seats;
  document.getElementById("t-status").value = t.status;
  openModal("trip-modal");
}

function saveTrip(e) {
  e.preventDefault();
  var data = {
    route: document.getElementById("t-route").value,
    time: document.getElementById("t-time").value,
    bus: document.getElementById("t-bus").value,
    plate: document.getElementById("t-plate").value.trim(),
    price: parseInt(document.getElementById("t-price").value, 10) || 0,
    seats: parseInt(document.getElementById("t-seats").value, 10) || 0,
    status: document.getElementById("t-status").value
  };
  if (!data.plate) { alert("Vui lòng nhập biển số xe."); return; }

  if (editingId) {
    var t = trips.find(function (x) { return x.id === editingId; });
    Object.assign(t, data);
    showToast("✓ Đã cập nhật chuyến " + data.route + " " + data.time);
  } else {
    data.id = nextId++;
    trips.push(data);
    showToast("✓ Đã thêm chuyến " + data.route + " " + data.time);
  }
  closeModal("trip-modal");
  renderTrips();
}

function deleteTrip(id) {
  var t = trips.find(function (x) { return x.id === id; });
  if (!t) return;
  if (confirm("Xóa chuyến " + t.route + " lúc " + t.time + "?\nThao tác này không thể hoàn tác.")) {
    trips = trips.filter(function (x) { return x.id !== id; });
    renderTrips();
    showToast("Đã xóa chuyến " + t.route + " " + t.time);
  }
}
