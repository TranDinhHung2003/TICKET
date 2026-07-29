package com.fbposter.shop.web;

import com.fbposter.shop.service.SepayWebhookService;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/sepay")
public class SepayWebhookController {

  private final SepayWebhookService sepayWebhookService;

  public SepayWebhookController(SepayWebhookService sepayWebhookService) {
    this.sepayWebhookService = sepayWebhookService;
  }

  @PostMapping("/webhook")
  public ResponseEntity<Map<String, Object>> webhook(
      @RequestHeader(value = "Authorization", required = false) String authorization,
      @RequestBody String body) {
    if (!sepayWebhookService.isAuthorized(authorization)) {
      return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("success", false));
    }
    try {
      sepayWebhookService.handle(body);
      return ResponseEntity.ok(Map.of("success", true));
    } catch (Exception e) {
      return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
          .body(Map.of("success", false, "error", e.getMessage()));
    }
  }
}
