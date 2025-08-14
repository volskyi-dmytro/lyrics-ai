package com.example.songmeaning.dto;

import java.time.Instant;

public record ErrorResponse(
    Instant timestamp,
    int status,
    String error,
    String message,
    String path
) {}
