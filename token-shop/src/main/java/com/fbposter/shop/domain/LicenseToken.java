package com.fbposter.shop.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "license_tokens")
public class LicenseToken {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 40)
    private String token;

    @ManyToOne(fetch = FetchType.LAZY)
    private UserAccount owner;

    @ManyToOne(fetch = FetchType.LAZY)
    private ShopOrder order;

    @Column(nullable = false)
    private Instant createdAt = Instant.now();

    @Column(nullable = false)
    private Instant expiresAt;

    @Column(nullable = false, length = 80)
    private String durationLabel;

    /** Số phút thời hạn theo gói khách mua — đồng hồ chạy từ lúc kích hoạt lần đầu */
    @Column(nullable = false, columnDefinition = "bigint default 0 not null")
    private long durationMinutes = 0;

    private boolean revoked = false;
    private String machineId;
    private String machineName;
    private String blockedMachineId;
    private String firstIp;
    private String lastIp;
    private Instant activatedAt;
    private Instant lastSeenAt;
    private int activateCount = 0;
    private String note;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getToken() { return token; }
    public void setToken(String token) { this.token = token; }
    public UserAccount getOwner() { return owner; }
    public void setOwner(UserAccount owner) { this.owner = owner; }
    public ShopOrder getOrder() { return order; }
    public void setOrder(ShopOrder order) { this.order = order; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
    public Instant getExpiresAt() { return expiresAt; }
    public void setExpiresAt(Instant expiresAt) { this.expiresAt = expiresAt; }
    public String getDurationLabel() { return durationLabel; }
    public void setDurationLabel(String durationLabel) { this.durationLabel = durationLabel; }
    public long getDurationMinutes() { return durationMinutes; }
    public void setDurationMinutes(long durationMinutes) { this.durationMinutes = durationMinutes; }
    public boolean isRevoked() { return revoked; }
    public void setRevoked(boolean revoked) { this.revoked = revoked; }
    public String getMachineId() { return machineId; }
    public void setMachineId(String machineId) { this.machineId = machineId; }
    public String getMachineName() { return machineName; }
    public void setMachineName(String machineName) { this.machineName = machineName; }
    public String getBlockedMachineId() { return blockedMachineId; }
    public void setBlockedMachineId(String blockedMachineId) { this.blockedMachineId = blockedMachineId; }
    public String getFirstIp() { return firstIp; }
    public void setFirstIp(String firstIp) { this.firstIp = firstIp; }
    public String getLastIp() { return lastIp; }
    public void setLastIp(String lastIp) { this.lastIp = lastIp; }
    public Instant getActivatedAt() { return activatedAt; }
    public void setActivatedAt(Instant activatedAt) { this.activatedAt = activatedAt; }
    public Instant getLastSeenAt() { return lastSeenAt; }
    public void setLastSeenAt(Instant lastSeenAt) { this.lastSeenAt = lastSeenAt; }
    public int getActivateCount() { return activateCount; }
    public void setActivateCount(int activateCount) { this.activateCount = activateCount; }
    public String getNote() { return note; }
    public void setNote(String note) { this.note = note; }
}
