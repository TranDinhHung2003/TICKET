/* Quản lý SEO — cấu hình Meta Title, Meta Description, Schema, Từ khóa cho từng trang */

var SEO_DEFAULTS = {
  "index.html": {
    title: "Xe Ghép & Taxi Thùy Nguyễn — Đặt Xe Ghép Miền Bắc, Đón Tận Nhà",
    description: "Xe ghép & taxi Thùy Nguyễn chuyên tuyến Hà Nội - Hải Phòng - Hạ Long - Ninh Bình - Sapa và taxi sân bay Nội Bài. Đi ghép chỉ từ 180.000đ/ghế, bao xe riêng 4-16 chỗ, đón trả tận nhà 24/7.",
    keywords: ["xe ghép miền Bắc", "xe ghép Hà Nội Hải Phòng", "taxi Nội Bài", "bao xe đường dài"],
    schema: '{\n  "@context": "https://schema.org",\n  "@type": "TaxiService",\n  "name": "Xe Ghép & Taxi Thùy Nguyễn",\n  "provider": {\n    "@type": "LocalBusiness",\n    "telephone": "+84912345678",\n    "aggregateRating": {\n      "@type": "AggregateRating",\n      "ratingValue": "4.9",\n      "reviewCount": "1573"\n    }\n  }\n}'
  },
  "booking.html": {
    title: "Đặt Xe Ghép & Taxi Online — Thùy Nguyễn | Chọn Ghế, Bao Xe, Thanh Toán Nhanh",
    description: "Đặt xe ghép và taxi online Thùy Nguyễn: chọn tuyến miền Bắc, chọn khung giờ, chọn ghế hoặc bao xe riêng, đón tận nhà chỉ trong 2 phút.",
    keywords: ["đặt xe ghép online", "bao xe taxi đường dài", "xe ghép Hà Nội Sapa"],
    schema: '{\n  "@context": "https://schema.org",\n  "@type": "WebPage",\n  "name": "Đặt xe ghép & taxi online",\n  "potentialAction": { "@type": "ReserveAction" }\n}'
  },
  "about.html": {
    title: "Về Chúng Tôi — Xe Ghép & Taxi Thùy Nguyễn | 10 Năm Phục Vụ Miền Bắc",
    description: "Tìm hiểu về Xe Ghép & Taxi Thùy Nguyễn: hành trình 10 năm phát triển tại miền Bắc, đội xe 60 chiếc 4-16 chỗ đời mới và cam kết đón đúng giờ, giá minh bạch.",
    keywords: ["giới thiệu xe ghép Thùy Nguyễn", "đội xe taxi đường dài", "cam kết chất lượng"],
    schema: '{\n  "@context": "https://schema.org",\n  "@type": "AboutPage",\n  "name": "Về Xe Ghép & Taxi Thùy Nguyễn"\n}'
  },
  "blog.html": {
    title: "Cẩm Nang Du Lịch Miền Bắc & Kinh Nghiệm Đi Xe Ghép — Blog Thùy Nguyễn",
    description: "Cẩm nang du lịch Sapa, Hạ Long, Ninh Bình; kinh nghiệm đi xe ghép, bảng giá các tuyến và mẹo đặt xe sân bay Nội Bài.",
    keywords: ["cẩm nang du lịch Sapa", "kinh nghiệm đi xe ghép", "blog xe ghép miền Bắc"],
    schema: '{\n  "@context": "https://schema.org",\n  "@type": "Blog",\n  "name": "Blog Xe Ghép & Taxi Thùy Nguyễn"\n}'
  },
  "contact.html": {
    title: "Liên Hệ — Xe Ghép & Taxi Thùy Nguyễn | Hotline 0912 345 678 (24/7)",
    description: "Liên hệ Xe Ghép & Taxi Thùy Nguyễn: hotline 0912 345 678 hoạt động 24/7, văn phòng tại Hà Nội, Hải Phòng và Sapa. Gửi góp ý trực tuyến.",
    keywords: ["liên hệ xe ghép Thùy Nguyễn", "hotline đặt xe ghép"],
    schema: '{\n  "@context": "https://schema.org",\n  "@type": "ContactPage",\n  "name": "Liên hệ Xe Ghép & Taxi Thùy Nguyễn"\n}'
  }
};

var STORAGE_KEY = "tn_seo_config_v2";
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
    "https://xeghepthuynguyen.vn/" + (page === "index.html" ? "" : page);

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
