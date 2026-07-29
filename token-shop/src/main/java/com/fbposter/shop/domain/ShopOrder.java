package com.fbposter.shop.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "orders", indexes = {
        @Index(name = "idx_orders_code", columnList = "paymentCode", unique = true)
})
public class ShopOrder {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 40)
    private String paymentCode;

    @ManyToOne(optional = false, fetch = FetchType.LAZY)
    private UserAccount user;

    @ManyToOne(optional = false, fetch = FetchType.EAGER)
    private ProductPlan plan;

    @Column(nullable = false)
    private long amountVnd;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private OrderStatus status = OrderStatus.PENDING;

    private Instant createdAt = Instant.now();
    private Instant expiresAt;
    private Instant paidAt;

    private String buyerEmail;
    private String buyerName;

    private String sepayTransactionId;
    private String transferContent;
    private Long transferAmount;

    /** Token đã cấp sau khi thanh toán */
    private String issuedToken;
    private Instant tokenExpiresAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getPaymentCode() { return paymentCode; }
    public void setPaymentCode(String paymentCode) { this.paymentCode = paymentCode; }
    public UserAccount getUser() { return user; }
    public void setUser(UserAccount user) { this.user = user; }
    public ProductPlan getPlan() { return plan; }
    public void setPlan(ProductPlan plan) { this.plan = plan; }
    public long getAmountVnd() { return amountVnd; }
    public void setAmountVnd(long amountVnd) { this.amountVnd = amountVnd; }
    public OrderStatus getStatus() { return status; }
    public void setStatus(OrderStatus status) { this.status = status; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
    public Instant getExpiresAt() { return expiresAt; }
    public void setExpiresAt(Instant expiresAt) { this.expiresAt = expiresAt; }
    public Instant getPaidAt() { return paidAt; }
    public void setPaidAt(Instant paidAt) { this.paidAt = paidAt; }
    public String getBuyerEmail() { return buyerEmail; }
    public void setBuyerEmail(String buyerEmail) { this.buyerEmail = buyerEmail; }
    public String getBuyerName() { return buyerName; }
    public void setBuyerName(String buyerName) { this.buyerName = buyerName; }
    public String getSepayTransactionId() { return sepayTransactionId; }
    public void setSepayTransactionId(String sepayTransactionId) { this.sepayTransactionId = sepayTransactionId; }
    public String getTransferContent() { return transferContent; }
    public void setTransferContent(String transferContent) { this.transferContent = transferContent; }
    public Long getTransferAmount() { return transferAmount; }
    public void setTransferAmount(Long transferAmount) { this.transferAmount = transferAmount; }
    public String getIssuedToken() { return issuedToken; }
    public void setIssuedToken(String issuedToken) { this.issuedToken = issuedToken; }
    public Instant getTokenExpiresAt() { return tokenExpiresAt; }
    public void setTokenExpiresAt(Instant tokenExpiresAt) { this.tokenExpiresAt = tokenExpiresAt; }
}
