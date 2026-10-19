package com.company.generated.config;

import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.converter.xml.MappingJackson2XmlHttpMessageConverter;

@Configuration
public class XmlMessageConverterConfig {

    @Bean
    public MappingJackson2XmlHttpMessageConverter mappingJackson2XmlHttpMessageConverter() {
        XmlMapper xmlMapper = new XmlMapper();
        return new MappingJackson2XmlHttpMessageConverter(xmlMapper);
    }
}
