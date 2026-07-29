package com.fbposter.shop.service;

import com.fbposter.shop.domain.Role;
import com.fbposter.shop.domain.UserAccount;
import com.fbposter.shop.repository.UserAccountRepository;
import java.util.Map;
import java.util.Optional;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {

  private final UserAccountRepository userRepo;
  private final MailOtpService otpService;
  private final PasswordEncoder passwordEncoder;

  public AuthService(
      UserAccountRepository userRepo, MailOtpService otpService, PasswordEncoder passwordEncoder) {
    this.userRepo = userRepo;
    this.otpService = otpService;
    this.passwordEncoder = passwordEncoder;
  }

  public Optional<UserAccount> findByEmail(String email) {
    return userRepo.findByEmailIgnoreCase(email);
  }

  @Transactional
  public void startRegister(String email, String fullName, String rawPassword) {
    email = email.trim().toLowerCase();
    if (userRepo.existsByEmailIgnoreCase(email)) {
      UserAccount existing = userRepo.findByEmailIgnoreCase(email).orElseThrow();
      if (existing.isEmailVerified()) {
        throw new IllegalArgumentException("Email đã được đăng ký");
      }
      existing.setFullName(fullName);
      existing.setPasswordHash(passwordEncoder.encode(rawPassword));
      userRepo.save(existing);
    } else {
      UserAccount u = new UserAccount();
      u.setEmail(email);
      u.setFullName(fullName);
      u.setPasswordHash(passwordEncoder.encode(rawPassword));
      u.setRole(Role.USER);
      u.setEmailVerified(false);
      u.setEnabled(true);
      userRepo.save(u);
    }
    otpService.sendOtp(email, "REGISTER");
  }

  @Transactional
  public UserAccount confirmRegister(String email, String otp) {
    email = email.trim().toLowerCase();
    if (!otpService.verifyOtp(email, "REGISTER", otp)) {
      throw new IllegalArgumentException("Mã OTP không đúng hoặc đã hết hạn");
    }
    UserAccount u =
        userRepo
            .findByEmailIgnoreCase(email)
            .orElseThrow(() -> new IllegalArgumentException("Tài khoản không tồn tại"));
    u.setEmailVerified(true);
    return userRepo.save(u);
  }

  public void resendRegisterOtp(String email) {
    email = email.trim().toLowerCase();
    UserAccount u =
        userRepo
            .findByEmailIgnoreCase(email)
            .orElseThrow(() -> new IllegalArgumentException("Email chưa đăng ký"));
    if (u.isEmailVerified()) {
      throw new IllegalArgumentException("Tài khoản đã xác minh");
    }
    otpService.sendOtp(email, "REGISTER");
  }

  @Transactional
  public UserAccount upsertGoogleUser(OAuth2User oauth2User) {
    Map<String, Object> attrs = oauth2User.getAttributes();
    String email = String.valueOf(attrs.getOrDefault("email", "")).trim().toLowerCase();
    String name = String.valueOf(attrs.getOrDefault("name", email));
    String googleId = String.valueOf(attrs.getOrDefault("sub", ""));
    if (email.isBlank() || "null".equals(email)) {
      throw new IllegalStateException("Google không trả về email");
    }

    Optional<UserAccount> byGoogle = userRepo.findByGoogleId(googleId);
    if (byGoogle.isPresent()) {
      return byGoogle.get();
    }

    Optional<UserAccount> byEmail = userRepo.findByEmailIgnoreCase(email);
    if (byEmail.isPresent()) {
      UserAccount u = byEmail.get();
      u.setGoogleId(googleId);
      u.setEmailVerified(true);
      if (u.getFullName() == null || u.getFullName().isBlank()) {
        u.setFullName(name);
      }
      return userRepo.save(u);
    }

    UserAccount u = new UserAccount();
    u.setEmail(email);
    u.setFullName(name);
    u.setGoogleId(googleId);
    u.setRole(Role.USER);
    u.setEmailVerified(true);
    u.setEnabled(true);
    return userRepo.save(u);
  }
}
