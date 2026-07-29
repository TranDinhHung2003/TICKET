package com.fbposter.shop.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "sepay_webhook_logs")
public class SepayWebhookLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private Long transactionId;

    @Lob
    @Column(nullable = false)
    private String bodyJson;

    private String paymentCode;
    private Long transferAmount;
    private String transferType;

    private Instant createdAt = Instant.now();

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getTransactionId() { return transactionId; }
    public void setTransactionId(Long transactionId) { this.transactionId = transactionId; }
    public String getBodyJson() { return bodyJson; }
    public void setBodyJson(String bodyJson) { this.bodyJson = bodyJson; }
    public String getPaymentCode() { return paymentCode; }
    public void setPaymentCode(String paymentCode) { this.paymentCode = paymentCode; }
    public Long getTransferAmount() { return transferAmount; }
    public void setTransferAmount(Long transferAmount) { this.transferAmount = transferAmount; }
    public String getTransferType() { return transferType; }
    public void setTransferType(String transferType) { this.transferType = transferType; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
