package com.example.songmeaning.advice;

import com.example.songmeaning.dto.ErrorResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;

@RestControllerAdvice
public class GlobalExceptionHandler {
  
  @ExceptionHandler(ResponseStatusException.class)
  public ResponseEntity<ErrorResponse> handleResponseStatus(
      ResponseStatusException ex,
      HttpServletRequest req
  ) {
    int statusCode = ex.getStatusCode().value();
    String reason = (ex.getStatusCode() instanceof HttpStatus hs) ? hs.getReasonPhrase() : "";
    
    return ResponseEntity.status(statusCode).body(new ErrorResponse(
        Instant.now(),
        statusCode,
        reason,
        ex.getReason() != null ? ex.getReason() : "An error occurred",
        req.getRequestURI()
    ));
  }

  @ExceptionHandler(HttpStatusCodeException.class)
    public ResponseEntity<ErrorResponse> handleHttpStatusCode(
            HttpStatusCodeException ex,
            HttpServletRequest req
    ) {
        var statusCode = ex.getStatusCode().value();
        var reasonPhrase = (ex.getStatusCode() instanceof HttpStatus hs)
                ? hs.getReasonPhrase()
                : ""; // fallback empty if not an HttpStatus
        var bodyText = ex.getResponseBodyAsString();

        return ResponseEntity.status(statusCode).body(new ErrorResponse(
                Instant.now(),
                statusCode,
                reasonPhrase,
                (bodyText == null || bodyText.isBlank()) ? ex.getMessage() : bodyText,
                req.getRequestURI()
        ));
    }

    @ExceptionHandler(RestClientResponseException.class)
  public ResponseEntity<ErrorResponse> handleRestClientResponse(RestClientResponseException ex,
                                                                HttpServletRequest req) {
    int statusCode = ex.getStatusCode().value();
    String reason = (ex.getStatusCode() instanceof HttpStatus hs) ? hs.getReasonPhrase() : "";
    String body = ex.getResponseBodyAsString();
    return ResponseEntity.status(statusCode).body(new ErrorResponse(
        Instant.now(), statusCode, reason,
        (body == null || body.isBlank()) ? ex.getMessage() : body,
        req.getRequestURI()
    ));
  }
}
