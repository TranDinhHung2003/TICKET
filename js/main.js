/* Xe Ghép & Taxi Thùy Nguyễn — script dùng chung cho giao diện khách hàng */

// Menu di động
document.addEventListener("DOMContentLoaded", function () {
  var toggle = document.querySelector(".nav-toggle");
  var links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", function () {
      links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", links.classList.contains("open") ? "true" : "false");
    });
  }

  // Đặt ngày mặc định cho ô chọn ngày là hôm nay
  document.querySelectorAll('input[type="date"]').forEach(function (input) {
    if (!input.value) {
      var today = new Date().toISOString().slice(0, 10);
      input.min = today;
      input.value = today;
    }
  });

  // Form liên hệ (demo, không có backend)
  var contactForm = document.getElementById("contact-form");
  if (contactForm) {
    contactForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var alertBox = document.getElementById("contact-alert");
      if (alertBox) {
        alertBox.classList.add("show");
        alertBox.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      contactForm.reset();
    });
  }
});

// Định dạng tiền Việt Nam
function formatVND(amount) {
  return amount.toLocaleString("vi-VN") + "đ";
}
