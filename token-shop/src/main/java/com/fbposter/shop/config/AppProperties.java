package com.fbposter.shop.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@ConfigurationProperties(prefix = "app")
public class AppProperties {
    private String name = "Facebook Group Poster";
    private String baseUrl = "http://localhost:8080";
    private String adminEmail = "admin@local.test";
    private String adminPassword = "Admin@123456";
    private String mailFrom = "noreply@fbposter.local";
    private int otpExpireMinutes = 10;
    private int orderExpireMinutes = 15;
    private Sepay sepay = new Sepay();

    public static class Sepay {
        private String apiKey = "change-me";
        private String bankCode = "MB";
        private String accountNumber = "0910108069999";
        private String accountName = "MB BANK";
        private String paymentPrefix = "FBPAY";

        public String getApiKey() { return apiKey; }
        public void setApiKey(String apiKey) { this.apiKey = apiKey; }
        public String getBankCode() { return bankCode; }
        public void setBankCode(String bankCode) { this.bankCode = bankCode; }
        public String getAccountNumber() { return accountNumber; }
        public void setAccountNumber(String accountNumber) { this.accountNumber = accountNumber; }
        public String getAccountName() { return accountName; }
        public void setAccountName(String accountName) { this.accountName = accountName; }
        public String getPaymentPrefix() { return paymentPrefix; }
        public void setPaymentPrefix(String paymentPrefix) { this.paymentPrefix = paymentPrefix; }
    }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getBaseUrl() { return baseUrl; }
    public void setBaseUrl(String baseUrl) { this.baseUrl = baseUrl; }
    public String getAdminEmail() { return adminEmail; }
    public void setAdminEmail(String adminEmail) { this.adminEmail = adminEmail; }
    public String getAdminPassword() { return adminPassword; }
    public void setAdminPassword(String adminPassword) { this.adminPassword = adminPassword; }
    public String getMailFrom() { return mailFrom; }
    public void setMailFrom(String mailFrom) { this.mailFrom = mailFrom; }
    public int getOtpExpireMinutes() { return otpExpireMinutes; }
    public void setOtpExpireMinutes(int otpExpireMinutes) { this.otpExpireMinutes = otpExpireMinutes; }
    public int getOrderExpireMinutes() { return orderExpireMinutes; }
    public void setOrderExpireMinutes(int orderExpireMinutes) { this.orderExpireMinutes = orderExpireMinutes; }
    public Sepay getSepay() { return sepay; }
    public void setSepay(Sepay sepay) { this.sepay = sepay; }
}
