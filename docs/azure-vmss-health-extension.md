# Azure VMSS Application Health Extension

Issue: #33

Azure Virtual Machine Scale Sets(VMSS)는 **Application Health Extension**으로 VM 내부에서
HTTP(S)/TCP 프로브를 수행해 인스턴스 상태를 판단하고(업그레이드/자동 복구 등)
오케스트레이션에 활용합니다.

이 프로젝트는 백엔드에 간단한 health endpoint를 제공합니다:

- Backend: `GET /healthz` → `200` + `{"ok": true}`

## 무엇을 구성해야 하나

Microsoft Learn 문서 기준으로, 확장은 아래 값을 설정합니다.

- `protocol`: `http` / `https` / `tcp`
- `port`: (http/https는 선택, tcp는 필수)
- `requestPath`: (http/https는 필수)

참고(공식 문서):

- <https://learn.microsoft.com/ko-kr/azure/virtual-machine-scale-sets/virtual-machine-scale-sets-health-extension>

> 주의: VMSS에는 “Application Health Extension”과
> “health probe(예: Load Balancer probe)” 중
> 하나의 원본만 상태 모니터링으로 사용할 수 있습니다.

## 이 프로젝트 권장 설정(v2 기반 Binary Health States)

가장 단순한 형태는 `/healthz`가 **항상 200을 반환**하도록 하고, VMSS 확장이 해당 경로를
주기적으로 조회하도록 설정하는 방식입니다.

`--version 2.0`을 사용하는 이유는 `gracePeriod`, `intervalInSeconds`,
`numberOfProbes` 같은 세부 프로브 설정을 사용하기 위해서입니다. 응답 본문이
`{"ApplicationHealthState":"..."}` 형태가 아니면 VMSS는 binary health behavior로
처리합니다(HTTP 200 = Healthy, 그 외 = Unhealthy).

### 포트 선택

- **권장:** public/ingress가 바라보는 포트에서 `/healthz`가 200이 되도록 구성
  - (컨테이너 기준) `deploy/traefik/dynamic.yaml`에서 `/healthz`를 백엔드로
    라우팅함
  - 따라서 Traefik edge 포트(예: 8080)로도 `/healthz` 확인 가능
- 대안: VM/인스턴스에서 백엔드 포트(예: 8000)를 직접 프로브하도록 네트워크를 열어두는 방식

### 예시 (Linux, Azure CLI)

아래는 문서의 schema를 기반으로 한 예시입니다. 실제 환경에서는 포트/경로/유예 시간을
서비스 특성에 맞게 조정하세요. `gracePeriod`는 초 단위입니다(예: `300` = 5분).

`extension.json`:

```json
{
  "protocol": "http",
  "port": 8080,
  "requestPath": "/healthz",
  "intervalInSeconds": 5,
  "numberOfProbes": 3,
  "gracePeriod": 300
}
```

적용:

```bash
az vmss extension set \
  --name ApplicationHealthLinux \
  --publisher Microsoft.ManagedServices \
  --version 2.0 \
  --resource-group <myVMScaleSetResourceGroup> \
  --vmss-name <myVMScaleSet> \
  --settings ./extension.json

az vmss update-instances \
  --resource-group <myVMScaleSetResourceGroup> \
  --name <myVMScaleSet> \
  --instance-ids "*"
```

## (선택) Rich Health States

Rich Health States는 응답 본문에 `{"ApplicationHealthState":"Healthy"}` 같은 형태를
요구합니다. 현재 `/healthz`는 단순 binary 형태(200 응답)만 제공합니다.

Rich Health States가 필요해지면 `/healthz` 응답 스키마 변경 대신, 별도의 endpoint(예:
`/vmss-health`)를 추가하는 방향이 안전합니다(기존 모니터링/테스트 호환성 유지).
