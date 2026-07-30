package com.fbposter.shop.config;

import com.fbposter.shop.domain.Role;
import com.fbposter.shop.domain.UserAccount;
import com.fbposter.shop.service.AuthService;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.client.authentication.OAuth2AuthenticationToken;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.stereotype.Component;

@Component
public class GoogleOAuth2SuccessHandler implements AuthenticationSuccessHandler {

  private final AuthService authService;

  public GoogleOAuth2SuccessHandler(AuthService authService) {
    this.authService = authService;
  }

  @Override
  public void onAuthenticationSuccess(
      HttpServletRequest request, HttpServletResponse response, org.springframework.security.core.Authentication authentication)
      throws IOException, ServletException {
    OAuth2User oauth2User = (OAuth2User) authentication.getPrincipal();
    UserAccount account = authService.upsertGoogleUser(oauth2User);
    var authorities = List.of(new SimpleGrantedAuthority("ROLE_" + account.getRole().name()));
    var token =
        new UsernamePasswordAuthenticationToken(account.getEmail(), "N/A", authorities);
    SecurityContextHolder.getContext().setAuthentication(token);
    String redirect = account.getRole() == Role.ADMIN ? "/admin" : "/account/orders";
    response.sendRedirect(redirect);
  }
}
