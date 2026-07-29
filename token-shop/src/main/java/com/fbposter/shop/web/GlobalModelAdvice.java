package com.fbposter.shop.web;

import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ModelAttribute;

@ControllerAdvice
public class GlobalModelAdvice {

  private final CurrentUser currentUser;

  public GlobalModelAdvice(CurrentUser currentUser) {
    this.currentUser = currentUser;
  }

  @ModelAttribute("currentUser")
  public Object currentUser() {
    return currentUser.orNull();
  }
}
