package com.example.songmeaning.controller;

import com.example.songmeaning.dto.SongRequest;
import com.example.songmeaning.dto.SongResponse;
import com.example.songmeaning.dto.AnalyzeStartResponse;
import com.example.songmeaning.service.PythonClient;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

@RestController
@RequestMapping("/api")
public class SongMeaningController {
  private final PythonClient client;
  public SongMeaningController(PythonClient client){ this.client = client; }

  @PostMapping("/analyze")
  public ResponseEntity<SongResponse> analyze(@Valid @RequestBody SongRequest req){
    return ResponseEntity.ok(client.analyze(req));
  }

  @PostMapping("/analyze/start")
  public ResponseEntity<AnalyzeStartResponse> analyzeStart(@Valid @RequestBody SongRequest req){
    return ResponseEntity.ok(client.analyzeStart(req));
  }

  @GetMapping(value = "/progress/{requestId}", produces = "text/event-stream")
  public void progressStream(@PathVariable String requestId, HttpServletResponse response) throws IOException {
    // Proxy the SSE stream from Python service
    String progressUrl = client.getProgressStreamUrl(requestId);
    
    response.setContentType("text/event-stream");
    response.setCharacterEncoding("UTF-8");
    response.setHeader("Cache-Control", "no-cache");
    response.setHeader("Connection", "keep-alive");
    response.setHeader("Access-Control-Allow-Origin", "*");
    response.setHeader("X-Accel-Buffering", "no"); // Disable nginx buffering if present
    
    try {
      URL url = new URL(progressUrl);
      HttpURLConnection connection = (HttpURLConnection) url.openConnection();
      connection.setRequestMethod("GET");
      connection.setRequestProperty("Accept", "text/event-stream");
      connection.setRequestProperty("Cache-Control", "no-cache");
      
      try (InputStream inputStream = connection.getInputStream()) {
        byte[] buffer = new byte[256]; // Smaller buffer for better streaming
        int bytesRead;
        while ((bytesRead = inputStream.read(buffer)) != -1) {
          response.getOutputStream().write(buffer, 0, bytesRead);
          response.getOutputStream().flush(); // Force flush after each write
          
          // Small delay to prevent overwhelming the client
          try {
            Thread.sleep(10);
          } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            break;
          }
        }
      }
    } catch (Exception e) {
      response.getWriter().write("data: {\"error\": \"Connection failed\"}\n\n");
      response.getWriter().flush();
    }
  }
}
