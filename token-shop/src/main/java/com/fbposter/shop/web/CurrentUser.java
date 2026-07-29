package com.fbposter.shop.web;

import com.fbposter.shop.domain.UserAccount;
import com.fbposter.shop.repository.UserAccountRepository;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;

@Component
public class CurrentUser {

  private final UserAccountRepository userRepo;

  public CurrentUser(UserAccountRepository userRepo) {
    this.userRepo = userRepo;
  }

  public UserAccount require() {
    Authentication auth = SecurityContextHolder.getContext().getAuthentication();
    if (auth == null || !auth.isAuthenticated() || "anonymousUser".equals(auth.getPrincipal())) {
      throw new IllegalStateException("Chưa đăng nhập");
    }
    String email = auth.getName();
    return userRepo
        .findByEmailIgnoreCase(email)
        .orElseThrow(() -> new IllegalStateException("Không tìm thấy tài khoản"));
  }

  public UserAccount orNull() {
    try {
      Authentication auth = SecurityContextHolder.getContext().getAuthentication();
      if (auth == null || !auth.isAuthenticated() || "anonymousUser".equals(auth.getPrincipal())) {
        return null;
      }
      return userRepo.findByEmailIgnoreCase(auth.getName()).orElse(null);
    } catch (Exception e) {
      return null;
    }
  }
}
