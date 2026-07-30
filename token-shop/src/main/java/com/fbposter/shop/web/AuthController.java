package com.fbposter.shop.web;

import com.fbposter.shop.domain.Role;
import com.fbposter.shop.domain.UserAccount;
import com.fbposter.shop.service.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import java.util.List;
import org.springframework.core.env.Environment;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

@Controller
public class AuthController {

  private final AuthService authService;
  private final Environment env;

  public AuthController(AuthService authService, Environment env) {
    this.authService = authService;
    this.env = env;
  }

  @GetMapping("/login")
  public String loginPage(Model model) {
    model.addAttribute("googleEnabled", isGoogleEnabled());
    return "login";
  }

  @GetMapping("/register")
  public String registerPage() {
    return "register";
  }

  @PostMapping("/register")
  public String registerSubmit(
      @RequestParam String email,
      @RequestParam String fullName,
      @RequestParam String password,
      @RequestParam String passwordConfirm,
      RedirectAttributes ra,
      HttpSession session) {
    if (!password.equals(passwordConfirm)) {
      ra.addFlashAttribute("error", "Mật khẩu xác nhận không khớp");
      return "redirect:/register";
    }
    if (password.length() < 6) {
      ra.addFlashAttribute("error", "Mật khẩu tối thiểu 6 ký tự");
      return "redirect:/register";
    }
    try {
      authService.startRegister(email, fullName, password);
      session.setAttribute("pendingEmail", email.trim().toLowerCase());
      ra.addFlashAttribute("success", "Đã gửi mã OTP về Gmail của bạn. Vui lòng nhập mã để hoàn tất đăng ký.");
      return "redirect:/register/verify";
    } catch (IllegalArgumentException ex) {
      ra.addFlashAttribute("error", ex.getMessage());
      return "redirect:/register";
    }
  }

  @GetMapping("/register/verify")
  public String verifyPage(HttpSession session, Model model) {
    Object email = session.getAttribute("pendingEmail");
    model.addAttribute("email", email == null ? "" : email);
    return "register-verify";
  }

  @PostMapping("/register/verify")
  public String verifySubmit(
      @RequestParam String email,
      @RequestParam String otp,
      HttpServletRequest request,
      RedirectAttributes ra) {
    try {
      UserAccount account = authService.confirmRegister(email, otp);
      autoLogin(account, request);
      ra.addFlashAttribute("success", "Đăng ký thành công!");
      return "redirect:/account/orders";
    } catch (IllegalArgumentException ex) {
      ra.addFlashAttribute("error", ex.getMessage());
      return "redirect:/register/verify";
    }
  }

  @PostMapping("/register/resend")
  public String resend(@RequestParam String email, RedirectAttributes ra, HttpSession session) {
    try {
      authService.resendRegisterOtp(email);
      session.setAttribute("pendingEmail", email.trim().toLowerCase());
      ra.addFlashAttribute("success", "Đã gửi lại mã OTP về Gmail");
    } catch (IllegalArgumentException ex) {
      ra.addFlashAttribute("error", ex.getMessage());
    }
    return "redirect:/register/verify";
  }

  private void autoLogin(UserAccount account, HttpServletRequest request) {
    var authorities = List.of(new SimpleGrantedAuthority("ROLE_" + account.getRole().name()));
    var token =
        new UsernamePasswordAuthenticationToken(account.getEmail(), "N/A", authorities);
    SecurityContextHolder.getContext().setAuthentication(token);
    HttpSession session = request.getSession(true);
    session.setAttribute(
        HttpSessionSecurityContextRepository.SPRING_SECURITY_CONTEXT_KEY,
        SecurityContextHolder.getContext());
  }

  private boolean isGoogleEnabled() {
    String id = env.getProperty("spring.security.oauth2.client.registration.google.client-id", "");
    return id != null && !id.isBlank() && !"disabled".equalsIgnoreCase(id);
  }
}
