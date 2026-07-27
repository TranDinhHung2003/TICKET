/* Quản lý SEO — cấu hình Meta Title, Meta Description, Schema, Từ khóa cho từng trang */

var SEO_DEFAULTS = {
  "index.html": {
    title: "Nhà Xe Thùy Nguyễn — Đặt Vé Xe Limousine & Giường Nằm Uy Tín",
    description: "Nhà Xe Thùy Nguyễn chuyên tuyến Sài Gòn - Đà Lạt - Nha Trang - Mũi Né - Cần Thơ. Xe limousine, giường nằm đời mới, đặt vé online nhanh chóng, đưa đón tận nơi.",
    keywords: ["nhà xe Thùy Nguyễn", "vé xe Sài Gòn Đà Lạt", "xe limousine", "đặt vé xe khách online"],
    schema: '{\n  "@context": "https://schema.org",\n  "@type": "BusCompany",\n  "name": "Nhà Xe Thùy Nguyễn",\n  "telephone": "+84909123456",\n  "aggregateRating": {\n    "@type": "AggregateRating",\n    "ratingValue": "4.9",\n    "reviewCount": "1286"\n  }\n}'
  },
  "booking.html": {
    title: "Đặt Vé Xe Online — Nhà Xe Thùy Nguyễn | Chọn Ghế, Thanh Toán Nhanh",
    description: "Đặt vé xe khách online Nhà Xe Thùy Nguyễn: chọn tuyến, chọn giờ chạy, chọn vị trí ghế và thanh toán chỉ trong 2 phút.",
    keywords: ["đặt vé xe online", "chọn ghế xe limousine", "vé xe Sài Gòn Đà Lạt"],
    schema: '{\n  "@context": "https://schema.org",\n  "@type": "WebPage",\n  "name": "Đặt vé xe online",\n  "potentialAction": { "@type": "ReserveAction" }\n}'
  },
  "about.html": {
    title: "Về Chúng Tôi — Nhà Xe Thùy Nguyễn | 12 Năm Vận Tải Hành Khách Uy Tín",
    description: "Tìm hiểu về Nhà Xe Thùy Nguyễn: hành trình 12 năm phát triển, đội xe 45 chiếc đời mới và cam kết chất lượng dịch vụ hàng đầu.",
    keywords: ["giới thiệu nhà xe", "đội xe limousine", "cam kết chất lượng"],
    schema: '{\n  "@context": "https://schema.org",\n  "@type": "AboutPage",\n  "name": "Về Nhà Xe Thùy Nguyễn"\n}'
  },
  "blog.html": {
    title: "Cẩm Nang Du Lịch & Kinh Nghiệm Đi Xe — Blog Nhà Xe Thùy Nguyễn",
    description: "Cẩm nang du lịch Đà Lạt, Nha Trang, Mũi Né; kinh nghiệm đi xe giường nằm, mẹo đặt vé giá tốt và thông tin tuyến đường mới nhất.",
    keywords: ["cẩm nang du lịch Đà Lạt", "kinh nghiệm đi xe giường nằm", "blog nhà xe"],
    schema: '{\n  "@context": "https://schema.org",\n  "@type": "Blog",\n  "name": "Blog Nhà Xe Thùy Nguyễn"\n}'
  },
  "contact.html": {
    title: "Liên Hệ — Nhà Xe Thùy Nguyễn | Hotline 0909 123 456 (24/7)",
    description: "Liên hệ Nhà Xe Thùy Nguyễn: hotline 0909 123 456 hoạt động 24/7, văn phòng tại TP.HCM, Đà Lạt và Nha Trang. Gửi góp ý trực tuyến.",
    keywords: ["liên hệ nhà xe", "hotline đặt vé xe"],
    schema: '{\n  "@context": "https://schema.org",\n  "@type": "ContactPage",\n  "name": "Liên hệ Nhà Xe Thùy Nguyễn"\n}'
  }
};

var STORAGE_KEY = "tn_seo_config";
var keywords = [];

function loadConfig() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch (e) {
    return {};
  }
}

function currentPage() {
  return document.getElementById("seo-page").value;
}

document.addEventListener("DOMContentLoaded", function () {
  loadPage();
  document.getElementById("seo-page").addEventListener("change", loadPage);
  document.getElementById("seo-title").addEventListener("input", refreshPreview);
  document.getElementById("seo-desc").addEventListener("input", refreshPreview);
  document.getElementById("kw-input").addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addKeyword();
    }
  });
});

function loadPage() {
  var page = currentPage();
  var saved = loadConfig()[page];
  var data = saved || SEO_DEFAULTS[page];
  document.getElementById("seo-title").value = data.title;
  document.getElementById("seo-desc").value = data.description;
  document.getElementById("seo-schema").value = data.schema;
  keywords = data.keywords.slice();
  renderKeywords();
  refreshPreview();
}

function renderKeywords() {
  var wrap = document.getElementById("kw-chips");
  wrap.innerHTML = "";
  keywords.forEach(function (kw, i) {
    var chip = document.createElement("span");
    chip.className = "chip";
    chip.innerHTML = kw + " <button type='button' aria-label='Xóa từ khóa' onclick='removeKeyword(" + i + ")'>✕</button>";
    wrap.appendChild(chip);
  });
}

function addKeyword() {
  var input = document.getElementById("kw-input");
  var value = input.value.replace(/,/g, "").trim();
  if (value && keywords.indexOf(value) < 0) {
    keywords.push(value);
    renderKeywords();
  }
  input.value = "";
}

function removeKeyword(index) {
  keywords.splice(index, 1);
  renderKeywords();
}

function refreshPreview() {
  var title = document.getElementById("seo-title").value;
  var desc = document.getElementById("seo-desc").value;
  var page = currentPage();

  document.getElementById("serp-title").textContent = title || "(Chưa có tiêu đề)";
  document.getElementById("serp-desc").textContent = desc || "(Chưa có mô tả)";
  document.getElementById("serp-url").textContent =
    "https://nhaxethuynguyen.vn/" + (page === "index.html" ? "" : page);

  updateCounter("title-counter", title.length, 60);
  updateCounter("desc-counter", desc.length, 160);
}

function updateCounter(id, length, max) {
  var el = document.getElementById(id);
  el.textContent = length + " / " + max + " ký tự" + (length > max ? " — vượt giới hạn khuyến nghị!" : "");
  el.classList.toggle("over", length > max);
}

function saveSeo() {
  var schemaText = document.getElementById("seo-schema").value.trim();
  if (schemaText) {
    try {
      JSON.parse(schemaText);
    } catch (e) {
      alert("Schema Markup không phải JSON hợp lệ:\n" + e.message);
      return;
    }
  }

  var config = loadConfig();
  config[currentPage()] = {
    title: document.getElementById("seo-title").value,
    description: document.getElementById("seo-desc").value,
    keywords: keywords,
    schema: schemaText
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  showToast("✓ Đã lưu cấu hình SEO cho " + currentPage());
}

function resetSeo() {
  if (!confirm("Khôi phục cấu hình SEO mặc định cho trang này?")) return;
  var config = loadConfig();
  delete config[currentPage()];
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  loadPage();
  showToast("Đã khôi phục cấu hình mặc định");
}
