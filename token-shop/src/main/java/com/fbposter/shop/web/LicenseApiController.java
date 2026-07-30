package com.fbposter.shop.web;

import com.fbposter.shop.service.LicenseService;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Map;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
public class LicenseApiController {

  private final LicenseService licenseService;

  public LicenseApiController(LicenseService licenseService) {
    this.licenseService = licenseService;
  }

  @PostMapping("/activate")
  public Map<String, Object> activate(
      @RequestBody Map<String, String> body, HttpServletRequest request) {
    String token = body.getOrDefault("token", "");
    String machineId = body.getOrDefault("machine_id", "");
    String machineName = body.getOrDefault("machine_name", "");
    String ip = clientIp(request);
    return licenseService.activate(token, machineId, machineName, ip);
  }

  @PostMapping("/verify")
  public Map<String, Object> verify(
      @RequestBody Map<String, String> body, HttpServletRequest request) {
    String token = body.getOrDefault("token", "");
    String machineId = body.getOrDefault("machine_id", "");
    String ip = clientIp(request);
    return licenseService.verify(token, machineId, ip);
  }

  private String clientIp(HttpServletRequest request) {
    String xff = request.getHeader("X-Forwarded-For");
    if (xff != null && !xff.isBlank()) {
      return xff.split(",")[0].trim();
    }
    return request.getRemoteAddr();
  }
}
