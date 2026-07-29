package com.fbposter.shop.service;

import com.fbposter.shop.config.AppProperties;
import com.fbposter.shop.domain.OrderStatus;
import com.fbposter.shop.domain.SepayWebhookLog;
import com.fbposter.shop.domain.ShopOrder;
import com.fbposter.shop.repository.SepayWebhookLogRepository;
import com.fbposter.shop.repository.ShopOrderRepository;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.Locale;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class SepayWebhookService {

  private final SepayWebhookLogRepository webhookLogRepository;
  private final ShopOrderRepository orderRepository;
  private final OrderService orderService;
  private final AppProperties props;
  private final ObjectMapper objectMapper;

  public SepayWebhookService(
      SepayWebhookLogRepository webhookLogRepository,
      ShopOrderRepository orderRepository,
      OrderService orderService,
      AppProperties props,
      ObjectMapper objectMapper) {
    this.webhookLogRepository = webhookLogRepository;
    this.orderRepository = orderRepository;
    this.orderService = orderService;
    this.props = props;
    this.objectMapper = objectMapper;
  }

  public boolean isAuthorized(String authorizationHeader) {
    String expected = props.getSepay().getApiKey();
    if (expected == null || expected.isBlank()) {
      return false;
    }
    if (authorizationHeader == null) {
      return false;
    }
    String h = authorizationHeader.trim();
    if (h.equals(expected)) {
      return true;
    }
    String lower = h.toLowerCase(Locale.ROOT);
    if (lower.startsWith("apikey ")) {
      return h.substring(7).trim().equals(expected);
    }
    if (lower.startsWith("bearer ")) {
      return h.substring(7).trim().equals(expected);
    }
    return false;
  }

  @Transactional
  public boolean handle(String rawBody) throws Exception {
    JsonNode root = objectMapper.readTree(rawBody);

    Long sepayId = null;
    if (root.has("id") && !root.get("id").isNull()) {
      sepayId = root.get("id").asLong();
    }
    if (sepayId != null && webhookLogRepository.existsByTransactionId(sepayId)) {
      return true;
    }

    String transferType = text(root, "transferType");
    String content = text(root, "content");
    String code = text(root, "code");
    Long amount = null;
    if (root.has("transferAmount") && !root.get("transferAmount").isNull()) {
      amount = root.get("transferAmount").asLong();
    }

    String paymentCode = resolvePaymentCode(code, content);

    SepayWebhookLog log = new SepayWebhookLog();
    if (sepayId == null) {
      sepayId = Instant.now().toEpochMilli();
    }
    log.setTransactionId(sepayId);
    log.setBodyJson(rawBody);
    log.setPaymentCode(paymentCode);
    log.setTransferAmount(amount);
    log.setTransferType(transferType);

    if (transferType == null || !transferType.equalsIgnoreCase("in")) {
      webhookLogRepository.save(log);
      return true;
    }

    if (paymentCode == null) {
      webhookLogRepository.save(log);
      return true;
    }

    Optional<ShopOrder> opt = orderRepository.findByPaymentCode(paymentCode);
    if (opt.isEmpty()) {
      webhookLogRepository.save(log);
      return true;
    }

    ShopOrder order = opt.get();
    if (order.getStatus() != OrderStatus.PENDING) {
      webhookLogRepository.save(log);
      return true;
    }

    if (order.getExpiresAt() != null && order.getExpiresAt().isBefore(Instant.now())) {
      order.setStatus(OrderStatus.EXPIRED);
      orderRepository.save(order);
      webhookLogRepository.save(log);
      return true;
    }

    if (amount == null || amount < order.getAmountVnd()) {
      webhookLogRepository.save(log);
      return true;
    }

    orderService.fulfillPaidOrder(order, String.valueOf(sepayId), amount, content);
    webhookLogRepository.save(log);
    return true;
  }

  private String resolvePaymentCode(String code, String content) {
    String prefix = props.getSepay().getPaymentPrefix().toUpperCase(Locale.ROOT);
    if (code != null && !code.isBlank()) {
      String c = code.trim().toUpperCase(Locale.ROOT);
      if (c.startsWith(prefix)) {
        return c;
      }
    }
    if (content == null) {
      return null;
    }
    Pattern p =
        Pattern.compile("(" + Pattern.quote(prefix) + "[A-Z0-9]+)", Pattern.CASE_INSENSITIVE);
    Matcher m = p.matcher(content.toUpperCase(Locale.ROOT));
    if (m.find()) {
      return m.group(1);
    }
    return null;
  }

  private static String text(JsonNode n, String field) {
    if (n == null || !n.has(field) || n.get(field).isNull()) {
      return null;
    }
    return n.get(field).asText();
  }
}
