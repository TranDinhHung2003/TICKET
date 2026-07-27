/* Thùy Nguyễn — logic trang đặt xe ghép & taxi (demo phía giao diện, chưa nối backend) */

var ROUTES = {
  "hn-hp": { name: "Hà Nội → Hải Phòng", seat: 250000, car4: 1000000, car7: 1300000, car16: 1800000, duration: "2 giờ", distance: "120 km" },
  "hp-hn": { name: "Hải Phòng → Hà Nội", seat: 250000, car4: 1000000, car7: 1300000, car16: 1800000, duration: "2 giờ", distance: "120 km" },
  "hn-hl": { name: "Hà Nội → Hạ Long", seat: 300000, car4: 1200000, car7: 1500000, car16: 2100000, duration: "2.5 giờ", distance: "160 km" },
  "hl-hn": { name: "Hạ Long → Hà Nội", seat: 300000, car4: 1200000, car7: 1500000, car16: 2100000, duration: "2.5 giờ", distance: "160 km" },
  "hn-nb": { name: "Hà Nội → Ninh Bình", seat: 250000, car4: 900000, car7: 1200000, car16: 1700000, duration: "1.5 giờ", distance: "95 km" },
  "nb-hn": { name: "Ninh Bình → Hà Nội", seat: 250000, car4: 900000, car7: 1200000, car16: 1700000, duration: "1.5 giờ", distance: "95 km" },
  "hn-sp": { name: "Hà Nội → Sapa", seat: 450000, car4: 1800000, car7: 2200000, car16: 3200000, duration: "5 giờ", distance: "320 km" },
  "sp-hn": { name: "Sapa → Hà Nội", seat: 450000, car4: 1800000, car7: 2200000, car16: 3200000, duration: "5 giờ", distance: "320 km" },
  "hn-nba": { name: "Hà Nội ↔ Sân bay Nội Bài", seat: 180000, car4: 350000, car7: 450000, car16: 700000, duration: "45 phút", distance: "30 km" }
};

var CAR_TYPES = {
  car4: { label: "Sedan 4 chỗ", desc: "Vios, Accent — tối đa 3 khách", icon: "🚗" },
  car7: { label: "SUV 7 chỗ", desc: "Xpander, Veloz — tối đa 6 khách", icon: "🚙" },
  car16: { label: "Limousine 9–16 chỗ", desc: "Solati — nhóm đông, nhiều hành lý", icon: "🚐" }
};

// Khung giờ xe ghép cố định hằng ngày
var TIME_SLOTS = [
  { time: "05:00", left: 4 },
  { time: "07:00", left: 2 },
  { time: "09:00", left: 6 },
  { time: "11:00", left: 0 },
  { time: "13:00", left: 5 },
  { time: "15:00", left: 3 },
  { time: "17:00", left: 6 },
  { time: "19:00", left: 1 }
];

// Ghế đã có khách trên xe 7 chỗ (dữ liệu minh hoạ)
var SOLD_SEATS = ["A2"];

var state = {
  service: "ghep",          // "ghep" | "private"
  time: "",
  seats: [],
  carType: "",
  payMethod: "Chuyển khoản"
};

function $(sel) { return document.querySelector(sel); }
function $all(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }

document.addEventListener("DOMContentLoaded", function () {
  // Nhận tham số URL từ trang chủ (?route=hn-hp hoặc ?from=hn&to=hp&service=...)
  var params = new URLSearchParams(window.location.search);
  var pre = params.get("route");
  if (!pre && params.get("from") && params.get("to")) {
    pre = params.get("from") + "-" + params.get("to");
  }
  if (pre && ROUTES[pre]) $("#route-select").value = pre;
  var preDate = params.get("date");
  if (preDate) $("#travel-date").value = preDate;
  if (params.get("service") === "private") selectService("private");

  renderTimeSlots();
  renderSeats();
  renderCarOptions();
  updateSummary();

  $("#route-select").addEventListener("change", function () {
    renderCarOptions();
    updateSummary();
  });
  $("#travel-date").addEventListener("change", updateSummary);
  $("#pickup-time").addEventListener("change", function () {
    state.time = this.value ? "Đón lúc " + this.value : "";
    updateSummary();
  });
  $all('input[name="pay"]').forEach(function (radio) {
    radio.addEventListener("change", function () {
      state.payMethod = radio.value;
      updateSummary();
    });
  });
});

/* ---------- Loại dịch vụ ---------- */
function selectService(service) {
  state.service = service;
  state.time = "";
  state.seats = [];
  state.carType = "";
  $all(".service-tab").forEach(function (tab) {
    tab.classList.toggle("selected", tab.dataset.service === service);
  });
  // Bước 2: xe ghép chọn khung giờ, bao xe chọn giờ đón tự do
  $("#slot-block").hidden = service !== "ghep";
  $("#pickup-block").hidden = service !== "private";
  // Bước 3: xe ghép chọn ghế, bao xe chọn loại xe
  $("#seat-block").hidden = service !== "ghep";
  $("#car-block").hidden = service !== "private";
  $("#step3-label").textContent = service === "ghep" ? "Chọn ghế" : "Chọn xe";
  $("#step3-title").textContent = service === "ghep" ? "Chọn vị trí ghế" : "Chọn loại xe bao riêng";
  $all(".time-slot").forEach(function (el) { el.classList.remove("selected"); });
  $all(".seat.picked").forEach(function (el) { el.classList.remove("picked"); });
  $all(".car-option").forEach(function (el) { el.classList.remove("selected"); });
  $("#pickup-time").value = "";
  updateSummary();
}

/* ---------- Khung giờ xe ghép ---------- */
function renderTimeSlots() {
  var wrap = $("#time-slots");
  wrap.innerHTML = "";
  TIME_SLOTS.forEach(function (slot) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "time-slot" + (slot.left === 0 ? " disabled" : "");
    btn.innerHTML = "<strong>" + slot.time + "</strong><span>Xe 7 chỗ ghép</span><span>" +
      (slot.left === 0 ? "Hết chỗ" : "Còn " + slot.left + " chỗ") + "</span>";
    if (slot.left > 0) {
      btn.addEventListener("click", function () {
        $all(".time-slot").forEach(function (el) { el.classList.remove("selected"); });
        btn.classList.add("selected");
        state.time = slot.time;
        updateSummary();
      });
    }
    wrap.appendChild(btn);
  });
}

/* ---------- Sơ đồ ghế xe 7 chỗ ---------- */
function renderSeats() {
  var cabin = $("#car-cabin");
  cabin.innerHTML = "";
  // Hàng 1: tài xế + ghế trước F1; hàng 2: A1-A3; hàng 3: B1-B3
  var layout = [
    [{ code: "", driver: true }, { gap: true }, { code: "F1" }],
    [{ code: "A1" }, { code: "A2" }, { code: "A3" }],
    [{ code: "B1" }, { code: "B2" }, { code: "B3" }]
  ];
  layout.forEach(function (row) {
    var rowDiv = document.createElement("div");
    rowDiv.className = "car-row";
    row.forEach(function (cell) {
      var seat = document.createElement("button");
      seat.type = "button";
      if (cell.gap) {
        seat.className = "seat gap";
        seat.tabIndex = -1;
      } else if (cell.driver) {
        seat.className = "seat driver";
        seat.textContent = "🧑‍✈️";
        seat.disabled = true;
        seat.setAttribute("aria-label", "Tài xế");
      } else {
        seat.textContent = cell.code;
        seat.className = "seat" + (SOLD_SEATS.indexOf(cell.code) >= 0 ? " sold" : "");
        if (SOLD_SEATS.indexOf(cell.code) < 0) {
          seat.addEventListener("click", function () {
            var idx = state.seats.indexOf(cell.code);
            if (idx >= 0) {
              state.seats.splice(idx, 1);
              seat.classList.remove("picked");
            } else {
              state.seats.push(cell.code);
              seat.classList.add("picked");
            }
            updateSummary();
          });
        }
      }
      rowDiv.appendChild(seat);
    });
    cabin.appendChild(rowDiv);
  });
}

/* ---------- Chọn loại xe (bao xe) ---------- */
function renderCarOptions() {
  var wrap = $("#car-options");
  wrap.innerHTML = "";
  var route = currentRoute();
  Object.keys(CAR_TYPES).forEach(function (key) {
    var ct = CAR_TYPES[key];
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "car-option" + (state.carType === key ? " selected" : "");
    btn.innerHTML =
      "<span class='co-icon' aria-hidden='true'>" + ct.icon + "</span>" +
      "<span class='co-info'><strong>" + ct.label + "</strong><span>" + ct.desc + "</span></span>" +
      "<span class='co-price'>" + (route ? formatVND(route[key]) : "—") + "</span>";
    btn.addEventListener("click", function () {
      state.carType = key;
      $all(".car-option").forEach(function (el) { el.classList.remove("selected"); });
      btn.classList.add("selected");
      updateSummary();
    });
    wrap.appendChild(btn);
  });
}

/* ---------- Tóm tắt & tổng tiền ---------- */
function currentRoute() {
  return ROUTES[$("#route-select").value] || null;
}

function computeTotal() {
  var route = currentRoute();
  if (!route) return 0;
  if (state.service === "ghep") return route.seat * state.seats.length;
  return state.carType ? route[state.carType] : 0;
}

function updateSummary() {
  var route = currentRoute();
  $("#sum-service").textContent = state.service === "ghep" ? "Xe ghép (theo ghế)" : "Bao xe riêng";
  $("#sum-route").textContent = route ? route.name : "Chưa chọn";
  $("#sum-date").textContent = $("#travel-date").value ? formatDate($("#travel-date").value) : "Chưa chọn";
  $("#sum-time").textContent = state.time || "Chưa chọn";

  if (state.service === "ghep") {
    $("#sum-detail-label").textContent = "Ghế";
    $("#sum-detail").textContent = state.seats.length ? state.seats.join(", ") : "Chưa chọn";
    $("#sum-unit").textContent = route ? formatVND(route.seat) + " /ghế" : "—";
  } else {
    $("#sum-detail-label").textContent = "Loại xe";
    $("#sum-detail").textContent = state.carType ? CAR_TYPES[state.carType].label : "Chưa chọn";
    $("#sum-unit").textContent = route && state.carType ? formatVND(route[state.carType]) + " /xe" : "—";
  }
  $("#sum-pay").textContent = state.payMethod;
  $("#sum-total").textContent = formatVND(computeTotal());
}

function formatDate(iso) {
  var parts = iso.split("-");
  return parts[2] + "/" + parts[1] + "/" + parts[0];
}

/* ---------- Điều hướng các bước ---------- */
function goToStep(step) {
  if (step > 1 && !currentRoute()) { alert("Vui lòng chọn tuyến đường."); return; }
  if (step > 1 && !$("#travel-date").value) { alert("Vui lòng chọn ngày đi."); return; }
  if (step > 2 && !state.time) {
    alert(state.service === "ghep" ? "Vui lòng chọn khung giờ xe chạy." : "Vui lòng chọn giờ đón mong muốn.");
    return;
  }
  if (step > 3) {
    if (state.service === "ghep" && state.seats.length === 0) { alert("Vui lòng chọn ít nhất 1 ghế."); return; }
    if (state.service === "private" && !state.carType) { alert("Vui lòng chọn loại xe."); return; }
  }

  $all(".booking-step-panel").forEach(function (panel) {
    panel.hidden = panel.dataset.step !== String(step);
  });
  $all(".booking-steps .step").forEach(function (el, i) {
    el.classList.toggle("active", i + 1 === step);
    el.classList.toggle("done", i + 1 < step);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ---------- Xác nhận ---------- */
function confirmBooking() {
  var name = $("#pax-name").value.trim();
  var phone = $("#pax-phone").value.trim();
  var pickup = $("#pax-pickup").value.trim();
  if (!name) { alert("Vui lòng nhập họ và tên."); return; }
  if (!/^0\d{9,10}$/.test(phone)) { alert("Số điện thoại không hợp lệ (bắt đầu bằng 0, gồm 10–11 số)."); return; }
  if (!pickup) { alert("Vui lòng nhập địa chỉ đón để tài xế đến tận nơi."); return; }

  var code = "TN" + Date.now().toString().slice(-8);
  $("#ticket-code").textContent = code;
  var detail = currentRoute().name + " • " + formatDate($("#travel-date").value) + " • " + state.time + " • ";
  detail += state.service === "ghep"
    ? "Ghế " + state.seats.join(", ")
    : CAR_TYPES[state.carType].label + " (bao xe)";
  $("#success-detail").textContent = detail;

  $all(".booking-step-panel").forEach(function (panel) { panel.hidden = true; });
  $("#success-panel").hidden = false;
  $all(".booking-steps .step").forEach(function (el) {
    el.classList.remove("active");
    el.classList.add("done");
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}
