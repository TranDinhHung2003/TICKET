/* Nhà Xe Thùy Nguyễn — logic trang đặt vé (demo phía giao diện, chưa nối backend) */

var ROUTES = {
  "sg-dl": { name: "Sài Gòn → Đà Lạt", price: 290000, duration: "7 giờ", distance: "310 km" },
  "dl-sg": { name: "Đà Lạt → Sài Gòn", price: 290000, duration: "7 giờ", distance: "310 km" },
  "sg-nt": { name: "Sài Gòn → Nha Trang", price: 320000, duration: "8 giờ", distance: "430 km" },
  "nt-sg": { name: "Nha Trang → Sài Gòn", price: 320000, duration: "8 giờ", distance: "430 km" },
  "sg-mt": { name: "Sài Gòn → Mũi Né", price: 220000, duration: "5 giờ", distance: "220 km" },
  "sg-ct": { name: "Sài Gòn → Cần Thơ", price: 180000, duration: "3.5 giờ", distance: "170 km" }
};

var TIME_SLOTS = [
  { time: "06:00", type: "Limousine 21 giường", left: 12 },
  { time: "08:30", type: "Limousine 21 giường", left: 7 },
  { time: "11:00", type: "Giường nằm 34 chỗ", left: 18 },
  { time: "13:30", type: "Limousine 21 giường", left: 0 },
  { time: "16:00", type: "Giường nằm 34 chỗ", left: 21 },
  { time: "20:00", type: "Limousine 21 giường", left: 9 },
  { time: "22:30", type: "Giường nằm 34 chỗ", left: 15 }
];

// Ghế đã bán (mã ghế) — dữ liệu minh hoạ
var SOLD_SEATS = ["A02", "A05", "B03", "B07", "C01", "C04"];

var state = { step: 1, route: "", date: "", time: "", seats: [], payMethod: "Chuyển khoản" };

function $(sel) { return document.querySelector(sel); }
function $all(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }

document.addEventListener("DOMContentLoaded", function () {
  // Nhận tuyến từ tham số URL (?route=sg-dl) do trang chủ chuyển sang
  var params = new URLSearchParams(window.location.search);
  var routeSelect = $("#route-select");
  var pre = params.get("route");
  if (!pre && params.get("from") && params.get("to")) {
    pre = params.get("from") + "-" + params.get("to");
  }
  if (pre && ROUTES[pre]) routeSelect.value = pre;
  var preDate = params.get("date");
  if (preDate) $("#travel-date").value = preDate;

  renderTimeSlots();
  renderSeats();
  updateSummary();

  $("#route-select").addEventListener("change", updateSummary);
  $("#travel-date").addEventListener("change", updateSummary);
  $all('input[name="pay"]').forEach(function (radio) {
    radio.addEventListener("change", function () {
      state.payMethod = radio.value;
      updateSummary();
    });
  });
});

function renderTimeSlots() {
  var wrap = $("#time-slots");
  wrap.innerHTML = "";
  TIME_SLOTS.forEach(function (slot) {
    var div = document.createElement("button");
    div.type = "button";
    div.className = "time-slot" + (slot.left === 0 ? " disabled" : "");
    div.innerHTML = "<strong>" + slot.time + "</strong><span>" + slot.type + "</span><span>" +
      (slot.left === 0 ? "Hết chỗ" : "Còn " + slot.left + " chỗ") + "</span>";
    if (slot.left > 0) {
      div.addEventListener("click", function () {
        $all(".time-slot").forEach(function (el) { el.classList.remove("selected"); });
        div.classList.add("selected");
        state.time = slot.time;
        updateSummary();
      });
    }
    wrap.appendChild(div);
  });
}

function renderSeats() {
  var grid = $("#seat-grid");
  grid.innerHTML = "";
  var cols = ["A", "B", "C"];
  for (var row = 1; row <= 7; row++) {
    cols.forEach(function (col) {
      var code = col + (row < 10 ? "0" + row : row);
      var seat = document.createElement("button");
      seat.type = "button";
      seat.textContent = code;
      seat.className = "seat" + (SOLD_SEATS.indexOf(code) >= 0 ? " sold" : "");
      if (SOLD_SEATS.indexOf(code) < 0) {
        seat.addEventListener("click", function () {
          var idx = state.seats.indexOf(code);
          if (idx >= 0) {
            state.seats.splice(idx, 1);
            seat.classList.remove("picked");
          } else if (state.seats.length < 5) {
            state.seats.push(code);
            seat.classList.add("picked");
          } else {
            alert("Mỗi lượt đặt tối đa 5 ghế. Vui lòng liên hệ hotline 0909 123 456 nếu đi theo đoàn.");
          }
          updateSummary();
        });
      }
      grid.appendChild(seat);
    });
  }
}

function currentRoute() {
  var key = $("#route-select").value;
  return ROUTES[key] || null;
}

function updateSummary() {
  var route = currentRoute();
  state.route = route ? route.name : "";
  state.date = $("#travel-date").value;

  $("#sum-route").textContent = state.route || "Chưa chọn";
  $("#sum-date").textContent = state.date ? formatDate(state.date) : "Chưa chọn";
  $("#sum-time").textContent = state.time || "Chưa chọn";
  $("#sum-seats").textContent = state.seats.length ? state.seats.join(", ") : "Chưa chọn";
  $("#sum-pay").textContent = state.payMethod;

  var unit = route ? route.price : 0;
  var total = unit * state.seats.length;
  $("#sum-unit").textContent = route ? formatVND(unit) : "—";
  $("#sum-total").textContent = formatVND(total);
}

function formatDate(iso) {
  var parts = iso.split("-");
  return parts[2] + "/" + parts[1] + "/" + parts[0];
}

function goToStep(step) {
  // Kiểm tra dữ liệu trước khi cho qua bước tiếp theo
  if (step > 1 && !currentRoute()) { alert("Vui lòng chọn tuyến đường."); return; }
  if (step > 1 && !$("#travel-date").value) { alert("Vui lòng chọn ngày đi."); return; }
  if (step > 2 && !state.time) { alert("Vui lòng chọn giờ khởi hành."); return; }
  if (step > 3 && state.seats.length === 0) { alert("Vui lòng chọn ít nhất 1 ghế."); return; }

  state.step = step;
  $all(".booking-step-panel").forEach(function (panel) {
    panel.hidden = panel.dataset.step !== String(step);
  });
  $all(".booking-steps .step").forEach(function (el, i) {
    el.classList.toggle("active", i + 1 === step);
    el.classList.toggle("done", i + 1 < step);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function confirmBooking() {
  var name = $("#pax-name").value.trim();
  var phone = $("#pax-phone").value.trim();
  if (!name) { alert("Vui lòng nhập họ và tên hành khách."); return; }
  if (!/^0\d{9,10}$/.test(phone)) { alert("Số điện thoại không hợp lệ (bắt đầu bằng 0, gồm 10–11 số)."); return; }

  var code = "TN" + Date.now().toString().slice(-8);
  $("#ticket-code").textContent = code;
  $("#success-detail").textContent =
    state.route + " • " + formatDate(state.date) + " • " + state.time + " • Ghế " + state.seats.join(", ");

  $all(".booking-step-panel").forEach(function (panel) { panel.hidden = true; });
  $("#success-panel").hidden = false;
  $all(".booking-steps .step").forEach(function (el) {
    el.classList.remove("active");
    el.classList.add("done");
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}
