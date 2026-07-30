package com.fbposter.shop.service;

import com.fbposter.shop.domain.Role;
import com.fbposter.shop.domain.UserAccount;
import com.fbposter.shop.repository.UserAccountRepository;
import java.util.Collection;
import java.util.List;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

@Service
public class AccountUserDetailsService implements UserDetailsService {

  private final UserAccountRepository userRepo;

  public AccountUserDetailsService(UserAccountRepository userRepo) {
    this.userRepo = userRepo;
  }

  @Override
  public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
    UserAccount account =
        userRepo
            .findByEmailIgnoreCase(username.trim())
            .orElseThrow(() -> new UsernameNotFoundException("Không tìm thấy tài khoản"));
    if (account.getPasswordHash() == null || account.getPasswordHash().isBlank()) {
      throw new UsernameNotFoundException("Tài khoản chỉ đăng nhập bằng Google");
    }
    Collection<? extends GrantedAuthority> authorities =
        List.of(new SimpleGrantedAuthority("ROLE_" + account.getRole().name()));
    return User.builder()
        .username(account.getEmail())
        .password(account.getPasswordHash())
        .disabled(!account.isEnabled())
        .accountExpired(false)
        .credentialsExpired(false)
        .accountLocked(!account.isEmailVerified() && account.getRole() != Role.ADMIN)
        .authorities(authorities)
        .build();
  }
}
