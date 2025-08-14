package com.example.songmeaning.dto;

import jakarta.validation.constraints.NotBlank;

public class SongRequest {
  @NotBlank private String artist;
  @NotBlank private String title;
  private String style;
  private String language = "en"; // Default to English

  public String getArtist() { return artist; }
  public void setArtist(String artist) { this.artist = artist; }
  public String getTitle() { return title; }
  public void setTitle(String title) { this.title = title; }
  public String getStyle() { return style; }
  public void setStyle(String style) { this.style = style; }
  public String getLanguage() { return language; }
  public void setLanguage(String language) { this.language = language; }
}
