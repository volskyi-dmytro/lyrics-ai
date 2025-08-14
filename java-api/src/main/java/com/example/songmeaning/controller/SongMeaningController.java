package com.example.songmeaning.controller;

import com.example.songmeaning.dto.SongRequest;
import com.example.songmeaning.dto.SongResponse;
import com.example.songmeaning.service.PythonClient;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class SongMeaningController {
  private final PythonClient client;
  public SongMeaningController(PythonClient client){ this.client = client; }

  @PostMapping("/analyze")
  public ResponseEntity<SongResponse> analyze(@Valid @RequestBody SongRequest req){
    return ResponseEntity.ok(client.analyze(req));
  }
}
