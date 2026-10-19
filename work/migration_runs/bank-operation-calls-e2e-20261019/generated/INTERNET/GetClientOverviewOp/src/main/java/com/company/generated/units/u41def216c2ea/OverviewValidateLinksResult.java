package com.company.generated.units.u41def216c2ea;

import com.company.generated.units.u5dfecf09ff9f.GetClientLinksRSFmtMapper;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;

public record OverviewValidateLinksResult(int returnCode, GetClientLinksRSFmtMapper.GetClientLinksResponse successResponse, StandardErrorRSFmtMapper.ErrorReply errorReply) {
    public boolean isSuccess() {
        return returnCode == 0;
    }

    public String nextTransition() {
        return isSuccess() ? "OverviewRefreshLinks" : "end";
    }
}