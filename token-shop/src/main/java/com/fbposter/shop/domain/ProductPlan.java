package com.fbposter.shop.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "product_plans")
public class ProductPlan {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 120)
    private String name;

    @Column(length = 500)
    private String description;

    private int minutes;
    private int hours;
    private int days;
    private int months;
    private int years;

    /** Giá VND */
    @Column(nullable = false)
    private long priceVnd;

    private boolean active = true;
    private int sortOrder = 0;

    private Instant updatedAt = Instant.now();

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public int getMinutes() { return minutes; }
    public void setMinutes(int minutes) { this.minutes = minutes; }
    public int getHours() { return hours; }
    public void setHours(int hours) { this.hours = hours; }
    public int getDays() { return days; }
    public void setDays(int days) { this.days = days; }
    public int getMonths() { return months; }
    public void setMonths(int months) { this.months = months; }
    public int getYears() { return years; }
    public void setYears(int years) { this.years = years; }
    public long getPriceVnd() { return priceVnd; }
    public void setPriceVnd(long priceVnd) { this.priceVnd = priceVnd; }
    public boolean isActive() { return active; }
    public void setActive(boolean active) { this.active = active; }
    public int getSortOrder() { return sortOrder; }
    public void setSortOrder(int sortOrder) { this.sortOrder = sortOrder; }
    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }

    public String durationLabel() {
        StringBuilder sb = new StringBuilder();
        if (years > 0) sb.append(years).append(" năm ");
        if (months > 0) sb.append(months).append(" tháng ");
        if (days > 0) sb.append(days).append(" ngày ");
        if (hours > 0) sb.append(hours).append(" giờ ");
        if (minutes > 0) sb.append(minutes).append(" phút ");
        String s = sb.toString().trim();
        return s.isEmpty() ? "30 ngày" : s;
    }

    /** Tổng phút thời hạn token theo gói khách chọn */
    public long totalMinutes() {
        long total = minutes
                + hours * 60L
                + days * 24L * 60
                + months * 30L * 24 * 60
                + years * 365L * 24 * 60;
        return total > 0 ? total : 30L * 24 * 60;
    }
}
