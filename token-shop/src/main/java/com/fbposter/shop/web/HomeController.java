package com.fbposter.shop.web;

import com.fbposter.shop.config.AppProperties;
import com.fbposter.shop.service.OrderService;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class HomeController {

  private final OrderService orderService;
  private final AppProperties props;
  private final Environment env;
  private final CurrentUser currentUser;

  public HomeController(
      OrderService orderService, AppProperties props, Environment env, CurrentUser currentUser) {
    this.orderService = orderService;
    this.props = props;
    this.env = env;
    this.currentUser = currentUser;
  }

  @GetMapping("/")
  public String home(Model model) {
    model.addAttribute("appName", props.getName());
    model.addAttribute("plans", orderService.listActivePlans());
    model.addAttribute("user", currentUser.orNull());
    model.addAttribute("googleEnabled", isGoogleEnabled());
    return "home";
  }

  private boolean isGoogleEnabled() {
    String id = env.getProperty("spring.security.oauth2.client.registration.google.client-id", "");
    return id != null && !id.isBlank() && !"disabled".equalsIgnoreCase(id);
  }
}
