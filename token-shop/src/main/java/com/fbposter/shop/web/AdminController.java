package com.fbposter.shop.web;

import com.fbposter.shop.config.AppProperties;
import com.fbposter.shop.domain.LicenseToken;
import com.fbposter.shop.domain.ProductPlan;
import com.fbposter.shop.domain.Role;
import com.fbposter.shop.domain.UserAccount;
import com.fbposter.shop.repository.LicenseTokenRepository;
import com.fbposter.shop.repository.ProductPlanRepository;
import com.fbposter.shop.repository.SaleLogRepository;
import com.fbposter.shop.repository.ShopOrderRepository;
import com.fbposter.shop.repository.UserAccountRepository;
import com.fbposter.shop.service.LicenseService;
import java.time.Instant;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

@Controller
@RequestMapping("/admin")
public class AdminController {

  private final SaleLogRepository saleLogRepository;
  private final ShopOrderRepository orderRepository;
  private final ProductPlanRepository planRepository;
  private final UserAccountRepository userRepository;
  private final LicenseTokenRepository tokenRepository;
  private final LicenseService licenseService;
  private final PasswordEncoder passwordEncoder;
  private final AppProperties props;

  public AdminController(
      SaleLogRepository saleLogRepository,
      ShopOrderRepository orderRepository,
      ProductPlanRepository planRepository,
      UserAccountRepository userRepository,
      LicenseTokenRepository tokenRepository,
      LicenseService licenseService,
      PasswordEncoder passwordEncoder,
      AppProperties props) {
    this.saleLogRepository = saleLogRepository;
    this.orderRepository = orderRepository;
    this.planRepository = planRepository;
    this.userRepository = userRepository;
    this.tokenRepository = tokenRepository;
    this.licenseService = licenseService;
    this.passwordEncoder = passwordEncoder;
    this.props = props;
  }

  @GetMapping({"", "/"})
  public String dashboard(Model model) {
    model.addAttribute("saleCount", saleLogRepository.count());
    model.addAttribute("orderCount", orderRepository.count());
    model.addAttribute("userCount", userRepository.count());
    model.addAttribute("tokenCount", tokenRepository.count());
    model.addAttribute("recentSales", saleLogRepository.findAllByOrderByCreatedAtDesc().stream().limit(10).toList());
    model.addAttribute("appName", props.getName());
    return "admin/dashboard";
  }

  @GetMapping("/sales")
  public String sales(Model model) {
    model.addAttribute("logs", saleLogRepository.findAllByOrderByCreatedAtDesc());
    return "admin/sales";
  }

  @GetMapping("/orders")
  public String orders(Model model) {
    model.addAttribute("orders", orderRepository.findAllByOrderByCreatedAtDesc());
    return "admin/orders";
  }

  @GetMapping("/plans")
  public String plans(Model model) {
    model.addAttribute("plans", planRepository.findAllByOrderBySortOrderAscIdAsc());
    return "admin/plans";
  }

  @PostMapping("/plans")
  public String createPlan(
      @RequestParam String name,
      @RequestParam(required = false) String description,
      @RequestParam(defaultValue = "0") int minutes,
      @RequestParam(defaultValue = "0") int hours,
      @RequestParam(defaultValue = "0") int days,
      @RequestParam(defaultValue = "0") int months,
      @RequestParam(defaultValue = "0") int years,
      @RequestParam long priceVnd,
      @RequestParam(defaultValue = "0") int sortOrder,
      RedirectAttributes ra) {
    ProductPlan p = new ProductPlan();
    p.setName(name);
    p.setDescription(description);
    p.setMinutes(minutes);
    p.setHours(hours);
    p.setDays(days);
    p.setMonths(months);
    p.setYears(years);
    p.setPriceVnd(priceVnd);
    p.setSortOrder(sortOrder);
    p.setActive(true);
    planRepository.save(p);
    ra.addFlashAttribute("success", "Đã thêm gói mới");
    return "redirect:/admin/plans";
  }

  @PostMapping("/plans/{id}")
  public String updatePlan(
      @PathVariable Long id,
      @RequestParam String name,
      @RequestParam(required = false) String description,
      @RequestParam(defaultValue = "0") int minutes,
      @RequestParam(defaultValue = "0") int hours,
      @RequestParam(defaultValue = "0") int days,
      @RequestParam(defaultValue = "0") int months,
      @RequestParam(defaultValue = "0") int years,
      @RequestParam long priceVnd,
      @RequestParam(defaultValue = "0") int sortOrder,
      @RequestParam(defaultValue = "false") boolean active,
      RedirectAttributes ra) {
    ProductPlan p = planRepository.findById(id).orElseThrow();
    p.setName(name);
    p.setDescription(description);
    p.setMinutes(minutes);
    p.setHours(hours);
    p.setDays(days);
    p.setMonths(months);
    p.setYears(years);
    p.setPriceVnd(priceVnd);
    p.setSortOrder(sortOrder);
    p.setActive(active);
    p.setUpdatedAt(Instant.now());
    planRepository.save(p);
    ra.addFlashAttribute("success", "Đã cập nhật bảng giá");
    return "redirect:/admin/plans";
  }

  @GetMapping("/users")
  public String users(Model model) {
    model.addAttribute("users", userRepository.findAll());
    return "admin/users";
  }

  @PostMapping("/users")
  public String createUser(
      @RequestParam String email,
      @RequestParam String fullName,
      @RequestParam String password,
      @RequestParam(defaultValue = "USER") String role,
      RedirectAttributes ra) {
    if (userRepository.existsByEmailIgnoreCase(email)) {
      ra.addFlashAttribute("error", "Email đã tồn tại");
      return "redirect:/admin/users";
    }
    UserAccount u = new UserAccount();
    u.setEmail(email.trim().toLowerCase());
    u.setFullName(fullName);
    u.setPasswordHash(passwordEncoder.encode(password));
    u.setRole(Role.valueOf(role));
    u.setEmailVerified(true);
    u.setEnabled(true);
    userRepository.save(u);
    ra.addFlashAttribute("success", "Đã tạo tài khoản");
    return "redirect:/admin/users";
  }

  @PostMapping("/users/{id}/toggle")
  public String toggleUser(@PathVariable Long id, RedirectAttributes ra) {
    UserAccount u = userRepository.findById(id).orElseThrow();
    u.setEnabled(!u.isEnabled());
    userRepository.save(u);
    ra.addFlashAttribute("success", "Đã cập nhật trạng thái tài khoản");
    return "redirect:/admin/users";
  }

  @GetMapping("/tokens")
  public String tokens(Model model) {
    model.addAttribute("tokens", tokenRepository.findAllByOrderByCreatedAtDesc());
    model.addAttribute("plans", planRepository.findAll());
    model.addAttribute("users", userRepository.findAll());
    return "admin/tokens";
  }

  @PostMapping("/tokens")
  public String createToken(
      @RequestParam(required = false) Long userId,
      @RequestParam(required = false) Long planId,
      @RequestParam(required = false) String note,
      RedirectAttributes ra) {
    UserAccount owner = userId == null ? null : userRepository.findById(userId).orElse(null);
    ProductPlan plan = planId == null ? null : planRepository.findById(planId).orElse(null);
    LicenseToken t = licenseService.adminCreate(owner, plan, note);
    ra.addFlashAttribute("success", "Đã tạo token: " + t.getToken());
    return "redirect:/admin/tokens";
  }

  @PostMapping("/tokens/{token}/revoke")
  public String revoke(@PathVariable String token, RedirectAttributes ra) {
    licenseService.revoke(token);
    ra.addFlashAttribute("success", "Đã thu hồi token");
    return "redirect:/admin/tokens";
  }

  @PostMapping("/tokens/{token}/reset")
  public String reset(@PathVariable String token, RedirectAttributes ra) {
    licenseService.resetMachine(token);
    ra.addFlashAttribute("success", "Đã cho phép đổi máy (máy cũ bị chặn)");
    return "redirect:/admin/tokens";
  }

  @GetMapping("/settings")
  public String settings(Model model) {
    model.addAttribute("props", props);
    return "admin/settings";
  }
}
