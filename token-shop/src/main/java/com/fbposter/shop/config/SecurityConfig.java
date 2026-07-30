package com.fbposter.shop.config;

import com.fbposter.shop.service.AccountUserDetailsService;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.servlet.util.matcher.PathPatternRequestMatcher;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {

  private final AccountUserDetailsService userDetailsService;
  private final GoogleOAuth2SuccessHandler googleSuccessHandler;
  private final Environment env;

  public SecurityConfig(
      AccountUserDetailsService userDetailsService,
      GoogleOAuth2SuccessHandler googleSuccessHandler,
      Environment env) {
    this.userDetailsService = userDetailsService;
    this.googleSuccessHandler = googleSuccessHandler;
    this.env = env;
  }

  @Bean
  public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    var path = PathPatternRequestMatcher.withDefaults();

    http.csrf(
            csrf ->
                csrf.ignoringRequestMatchers(
                    path.matcher("/api/sepay/webhook"),
                    path.matcher("/api/v1/**"),
                    path.matcher("/h2/**")))
        .headers(h -> h.frameOptions(f -> f.sameOrigin()))
        .authorizeHttpRequests(
            auth ->
                auth.requestMatchers(
                        "/",
                        "/css/**",
                        "/js/**",
                        "/images/**",
                        "/login",
                        "/register",
                        "/register/**",
                        "/error",
                        "/h2/**",
                        "/api/sepay/webhook",
                        "/api/v1/**")
                    .permitAll()
                    .requestMatchers("/admin/**")
                    .hasRole("ADMIN")
                    .requestMatchers("/checkout/**", "/account/**", "/buy/**")
                    .authenticated()
                    .anyRequest()
                    .authenticated())
        .formLogin(
            form ->
                form.loginPage("/login")
                    .usernameParameter("email")
                    .passwordParameter("password")
                    .defaultSuccessUrl("/account/orders", true)
                    .failureUrl("/login?error")
                    .permitAll())
        .logout(
            logout ->
                logout
                    .logoutRequestMatcher(path.matcher(HttpMethod.POST, "/logout"))
                    .logoutSuccessUrl("/?logout")
                    .permitAll())
        .userDetailsService(userDetailsService);

    if (isGoogleEnabled()) {
      http.oauth2Login(
          oauth ->
              oauth
                  .loginPage("/login")
                  .successHandler(googleSuccessHandler)
                  .failureUrl("/login?oauth_error"));
    }

    return http.build();
  }

  private boolean isGoogleEnabled() {
    String id = env.getProperty("spring.security.oauth2.client.registration.google.client-id", "");
    return id != null
        && !id.isBlank()
        && !"disabled".equalsIgnoreCase(id)
        && !id.startsWith("your-");
  }
}
