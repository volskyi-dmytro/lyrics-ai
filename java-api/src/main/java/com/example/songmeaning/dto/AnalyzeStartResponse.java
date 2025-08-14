package com.example.songmeaning.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class AnalyzeStartResponse {
  @JsonProperty("request_id")
  private String requestId;

  public AnalyzeStartResponse() {}

  public AnalyzeStartResponse(String requestId) {
    this.requestId = requestId;
  }

  public String getRequestId() {
    return requestId;
  }

  public void setRequestId(String requestId) {
    this.requestId = requestId;
  }
}