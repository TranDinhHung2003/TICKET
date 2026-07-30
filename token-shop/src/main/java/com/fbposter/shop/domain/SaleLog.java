package com.fbposter.shop.domain;

import jakarta.persistence.*;
import java.time.Instant;

/** Nhật ký mua bán rõ ràng cho admin */
@Entity
@Table(name = "sale_logs")
public class SaleLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Instant createdAt = Instant.now();

    private String buyerEmail;
    private String buyerName;
    private Long userId;
    private Long orderId;
    private String paymentCode;
    private String planName;
    private String durationLabel;
    private long amountVnd;
    private String issuedToken;
    private Instant tokenExpiresAt;
    private String note;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
    public String getBuyerEmail() { return buyerEmail; }
    public void setBuyerEmail(String buyerEmail) { this.buyerEmail = buyerEmail; }
    public String getBuyerName() { return buyerName; }
    public void setBuyerName(String buyerName) { this.buyerName = buyerName; }
    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }
    public Long getOrderId() { return orderId; }
    public void setOrderId(Long orderId) { this.orderId = orderId; }
    public String getPaymentCode() { return paymentCode; }
    public void setPaymentCode(String paymentCode) { this.paymentCode = paymentCode; }
    public String getPlanName() { return planName; }
    public void setPlanName(String planName) { this.planName = planName; }
    public String getDurationLabel() { return durationLabel; }
    public void setDurationLabel(String durationLabel) { this.durationLabel = durationLabel; }
    public long getAmountVnd() { return amountVnd; }
    public void setAmountVnd(long amountVnd) { this.amountVnd = amountVnd; }
    public String getIssuedToken() { return issuedToken; }
    public void setIssuedToken(String issuedToken) { this.issuedToken = issuedToken; }
    public Instant getTokenExpiresAt() { return tokenExpiresAt; }
    public void setTokenExpiresAt(Instant tokenExpiresAt) { this.tokenExpiresAt = tokenExpiresAt; }
    public String getNote() { return note; }
    public void setNote(String note) { this.note = note; }
}
