package com.example.songmeaning.service;

import com.example.songmeaning.dto.SongRequest;
import com.example.songmeaning.dto.SongResponse;
import com.example.songmeaning.dto.AnalyzeStartResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class PythonClient {
  private final RestClient http;
  private final String baseUrl;
  private final ObjectMapper objectMapper;

  public PythonClient(RestClient http, @Value("${ai.base-url:http://localhost:8000}") String baseUrl, ObjectMapper objectMapper){
    this.http = http; 
    this.baseUrl = baseUrl;
    this.objectMapper = objectMapper;
  }

  public SongResponse analyze(SongRequest req){
    try {
      return http.post().uri(baseUrl + "/analyze")
          .contentType(MediaType.APPLICATION_JSON)
          .accept(MediaType.APPLICATION_JSON)
          .body(req)
          .retrieve()
          .body(SongResponse.class);
    } catch (RestClientResponseException ex) {
      // Extract friendly message from JSON error response
      HttpStatusCode status = ex.getStatusCode();
      String body = ex.getResponseBodyAsString();
      String friendlyMessage = extractFriendlyMessage(body, ex.getMessage());
      throw new ResponseStatusException(status, friendlyMessage);
    }
  }

  public AnalyzeStartResponse analyzeStart(SongRequest req){
    try {
      return http.post().uri(baseUrl + "/analyze/start")
          .contentType(MediaType.APPLICATION_JSON)
          .accept(MediaType.APPLICATION_JSON)
          .body(req)
          .retrieve()
          .body(AnalyzeStartResponse.class);
    } catch (RestClientResponseException ex) {
      HttpStatusCode status = ex.getStatusCode();
      String body = ex.getResponseBodyAsString();
      String friendlyMessage = extractFriendlyMessage(body, ex.getMessage());
      throw new ResponseStatusException(status, friendlyMessage);
    }
  }

  public String getProgressStreamUrl(String requestId) {
    return baseUrl + "/progress/" + requestId;
  }

  private String extractFriendlyMessage(String jsonBody, String fallback) {
    if (jsonBody == null || jsonBody.isBlank()) {
      return fallback;
    }
    
    try {
      // Try to parse JSON and extract the "detail" field which contains the friendly message
      JsonNode root = objectMapper.readTree(jsonBody);
      JsonNode detailNode = root.get("detail");
      if (detailNode != null && !detailNode.isNull()) {
        String detail = detailNode.asText();
        if (!detail.isBlank()) {
          return "❌ " + detail;
        }
      }
    } catch (Exception ignored) {
      // If JSON parsing fails, fall back to the original message
    }
    
    return fallback;
  }
}
