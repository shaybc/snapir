package com.company.generated.support.format;

import java.time.LocalTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Date;
import java.util.List;
import java.util.Objects;

/** Example native time formatter with explicit pattern and Date-to-time timezone. */
public final class TimeFieldFormatter extends AbstractFieldFormatter<Object> {
    private final DateTimeFormatter pattern;
    private final ZoneId zone;

    public TimeFieldFormatter(String dataName, DateTimeFormatter pattern, ZoneId zone,
                              List<ValueDecorator> decorators) {
        super(dataName, decorators);
        this.pattern = Objects.requireNonNull(pattern);
        this.zone = Objects.requireNonNull(zone);
    }

    @Override
    protected String formatValue(Object value) {
        LocalTime time;
        if (value instanceof LocalTime localTime) time = localTime;
        else if (value instanceof Date date) time = date.toInstant().atZone(zone).toLocalTime();
        else throw new IllegalArgumentException("Expected LocalTime or Date");
        return pattern.format(time);
    }

    /** Native parsing produces LocalTime; any legacy Date adapter is a separate decision. */
    @Override
    protected Object unformatValue(String value) {
        return value.isBlank() ? null : LocalTime.parse(value, pattern);
    }
}
