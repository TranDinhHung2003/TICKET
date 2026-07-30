package com.fbposter.shop.service;

import com.fbposter.shop.config.AppProperties;
import com.fbposter.shop.domain.LicenseToken;
import com.fbposter.shop.domain.OrderStatus;
import com.fbposter.shop.domain.ProductPlan;
import com.fbposter.shop.domain.SaleLog;
import com.fbposter.shop.domain.ShopOrder;
import com.fbposter.shop.domain.UserAccount;
import com.fbposter.shop.repository.ProductPlanRepository;
import com.fbposter.shop.repository.SaleLogRepository;
import com.fbposter.shop.repository.ShopOrderRepository;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class OrderService {

  private final ShopOrderRepository orderRepository;
  private final ProductPlanRepository planRepository;
  private final SaleLogRepository saleLogRepository;
  private final LicenseService licenseService;
  private final MailOtpService mailService;
  private final AppProperties props;

  public OrderService(
      ShopOrderRepository orderRepository,
      ProductPlanRepository planRepository,
      SaleLogRepository saleLogRepository,
      LicenseService licenseService,
      MailOtpService mailService,
      AppProperties props) {
    this.orderRepository = orderRepository;
    this.planRepository = planRepository;
    this.saleLogRepository = saleLogRepository;
    this.licenseService = licenseService;
    this.mailService = mailService;
    this.props = props;
  }

  public List<ProductPlan> listActivePlans() {
    return planRepository.findByActiveTrueOrderBySortOrderAscIdAsc();
  }

  public List<ShopOrder> ordersOf(UserAccount user) {
    return orderRepository.findByUserOrderByCreatedAtDesc(user);
  }

  public ShopOrder requireOwned(Long orderId, UserAccount user) {
    ShopOrder order =
        orderRepository
            .findById(orderId)
            .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy đơn hàng"));
    if (!order.getUser().getId().equals(user.getId())) {
      throw new IllegalArgumentException("Bạn không có quyền xem đơn này");
    }
    return order;
  }

  @Transactional
  public ShopOrder createOrder(UserAccount buyer, Long planId) {
    ProductPlan plan =
        planRepository
            .findById(planId)
            .filter(ProductPlan::isActive)
            .orElseThrow(() -> new IllegalArgumentException("Gói không tồn tại hoặc đã tắt"));
    ShopOrder order = new ShopOrder();
    order.setUser(buyer);
    order.setPlan(plan);
    order.setAmountVnd(plan.getPriceVnd());
    order.setPaymentCode(newPaymentCode());
    order.setStatus(OrderStatus.PENDING);
    order.setBuyerEmail(buyer.getEmail());
    order.setBuyerName(buyer.getFullName());
    order.setExpiresAt(Instant.now().plus(props.getOrderExpireMinutes(), ChronoUnit.MINUTES));
    return orderRepository.save(order);
  }

  public String buildQrUrl(ShopOrder order) {
    String bank = URLEncoder.encode(props.getSepay().getBankCode(), StandardCharsets.UTF_8);
    String acc = URLEncoder.encode(props.getSepay().getAccountNumber(), StandardCharsets.UTF_8);
    String des = URLEncoder.encode(order.getPaymentCode(), StandardCharsets.UTF_8);
    return "https://img.vietqr.io/image/"
        + bank
        + "-"
        + acc
        + "-compact2.png?amount="
        + order.getAmountVnd()
        + "&addInfo="
        + des
        + "&accountName="
        + URLEncoder.encode(props.getSepay().getAccountName(), StandardCharsets.UTF_8);
  }

  @Transactional
  public ShopOrder fulfillPaidOrder(
      ShopOrder order, String sepayTxnId, Long transferAmount, String transferContent) {
    if (order.getStatus() == OrderStatus.PAID) {
      return order;
    }
    if (order.getStatus() == OrderStatus.CANCELLED || order.getStatus() == OrderStatus.EXPIRED) {
      throw new IllegalStateException("Đơn đã hết hạn hoặc đã huỷ");
    }

    LicenseToken token = licenseService.issueForOrder(order);

    order.setStatus(OrderStatus.PAID);
    order.setPaidAt(Instant.now());
    order.setSepayTransactionId(sepayTxnId);
    order.setTransferAmount(transferAmount);
    order.setTransferContent(transferContent);
    order.setIssuedToken(token.getToken());
    order.setTokenExpiresAt(token.getExpiresAt());
    orderRepository.save(order);

    SaleLog log = new SaleLog();
    log.setBuyerEmail(order.getBuyerEmail());
    log.setBuyerName(order.getBuyerName());
    log.setUserId(order.getUser().getId());
    log.setOrderId(order.getId());
    log.setPaymentCode(order.getPaymentCode());
    log.setPlanName(order.getPlan().getName());
    log.setDurationLabel(order.getPlan().durationLabel());
    log.setAmountVnd(order.getAmountVnd());
    log.setIssuedToken(token.getToken());
    log.setTokenExpiresAt(token.getExpiresAt());
    log.setNote("SePay txn=" + sepayTxnId);
    saleLogRepository.save(log);

    mailService.sendTokenEmail(
        order.getBuyerEmail(),
        token.getToken(),
        order.getPlan().getName(),
        order.getPlan().durationLabel(),
        token.getExpiresAt());
    return order;
  }

  private String newPaymentCode() {
    String prefix = props.getSepay().getPaymentPrefix().toUpperCase(Locale.ROOT);
    String raw = UUID.randomUUID().toString().replace("-", "").substring(0, 10).toUpperCase(Locale.ROOT);
    return prefix + raw;
  }
}
