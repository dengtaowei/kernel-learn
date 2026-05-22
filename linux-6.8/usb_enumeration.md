# USB 2.0 典型枚举流程（Token / DATA0·DATA1 / ACK，不含 NAK）

参与者为 **Host** 与 **Device**。每笔控制传输均符合规范中的 SETUP、可选数据阶段、状态阶段；**GET_DESCRIPTOR** 类请求的数据阶段为 **IN**，状态为 **OUT + DATA1(ZLP)**；**SET_ADDRESS** / **SET_CONFIGURATION** 无数据阶段，状态阶段为 **IN + 设备 DATA1(ZLP)**。


```mermaid
sequenceDiagram
    autonumber
    participant H as Host
    participant D as Device

    rect rgb(245, 245, 245)
    Note over H,D: 物理层 / 状态（非 SETUP 三段式）
    Note right of D: 上电或插入后：总线复位、速度协商（LS/FS/HS）<br/>设备在默认地址 0、端点 0 应答控制传输
    end

    rect rgb(230, 240, 255)
    Note over H,D: ① GET_DESCRIPTOR（DEVICE）先取 8 字节 — 得到 bMaxPacketSize0（地址 0）
    H->>D: SETUP + DATA0（GET_DESCRIPTOR / DEVICE / wLength=8）
    D-->>H: ACK
    H->>D: IN
    D-->>H: DATA1（设备描述符前 8 字节）
    H-->>D: ACK
    H->>D: OUT + DATA1（ZLP）
    D-->>H: ACK
    end

    rect rgb(255, 240, 230)
    Note over H,D: ② SET_ADDRESS — 无数据阶段（地址仍为 0，直到本笔结束）
    H->>D: SETUP + DATA0（SET_ADDRESS / wValue=新地址）
    D-->>H: ACK
    H->>D: IN
    D-->>H: DATA1（ZLP，状态阶段）
    H-->>D: ACK
    end

    rect rgb(245, 245, 245)
    Note over H,D: 主机按规范等待 ≥10 ms，之后所有 Token 使用新设备地址
    end

    rect rgb(230, 240, 255)
    Note over H,D: ③ GET_DESCRIPTOR（DEVICE）读完整设备描述符（地址 0）
    H->>D: SETUP + DATA0（GET_DESCRIPTOR / DEVICE / wLength=18 或更大）
    D-->>H: ACK
    H->>D: IN
    D-->>H: DATA1（设备描述符第 1 段）
    H-->>D: ACK
    opt 描述符超过 EP0 单包最大长度时
        H->>D: IN
        D-->>H: DATA0（第 2 段）
        H-->>D: ACK
        Note over H,D: 若有更多包：IN ↔ DATA1 / DATA0 ↔ ACK 交替直至短包或长度满足 wLength
    end
    H->>D: OUT + DATA1（ZLP）
    D-->>H: ACK
    end

    rect rgb(230, 255, 230)
    Note over H,D: ④ GET_DESCRIPTOR（CONFIGURATION）按 wTotalLength 读整棵配置树（新地址）
    H->>D: SETUP + DATA0（GET_DESCRIPTOR / CONFIGURATION index=0 / wLength=wTotalLength）
    D-->>H: ACK
    H->>D: IN
    D-->>H: DATA1（配置数据第 1 段）
    H-->>D: ACK
    loop 直到发满 wTotalLength（多包时 DATA0/DATA1 交替）
        H->>D: IN
        D-->>H: DATA0 或 DATA1（下一段）
        H-->>D: ACK
    end
    H->>D: OUT + DATA1（ZLP）
    D-->>H: ACK
    end

    rect rgb(255, 245, 230)
    Note over H,D: ⑤ GET_DESCRIPTOR（STRING 索引 0）— 取语言 ID 表（新地址）
    H->>D: SETUP + DATA0（GET_DESCRIPTOR / STRING index=0 / wIndex=0 / wLength=典型 4～255）
    D-->>H: ACK
    H->>D: IN
    D-->>H: DATA1（LANGID 表）
    H-->>D: ACK
    H->>D: OUT + DATA1（ZLP）
    D-->>H: ACK
    end

    rect rgb(255, 245, 230)
    Note over H,D: ⑥ GET_DESCRIPTOR（STRING）— 按设备描述符里 iManufacturer / iProduct / iSerial 等索引与 LANGID 读字符串（新地址，常重复多笔）
    loop 每个非 0 的字符串索引（及主机需要的语言）
        H->>D: SETUP + DATA0（GET_DESCRIPTOR / STRING / wIndex=LANGID / wLength=…）
        D-->>H: ACK
        H->>D: IN
        D-->>H: DATA1（Unicode 字符串，可能多包）
        H-->>D: ACK
        opt 字符串较长
            H->>D: IN
            D-->>H: DATA0 或 DATA1（续）
            H-->>D: ACK
        end
        H->>D: OUT + DATA1（ZLP）
        D-->>H: ACK
    end
    end

    rect rgb(240, 230, 255)
    Note over H,D: ⑦ SET_CONFIGURATION（值为 1，常见）— 无数据阶段，选中配置（新地址）
    H->>D: SETUP + DATA0（SET_CONFIGURATION / wValue=1）
    D-->>H: ACK
    H->>D: IN
    D-->>H: DATA1（ZLP，状态阶段）
    H-->>D: ACK
    end

    rect rgb(245, 245, 245)
    Note over H,D: 枚举核心结束；之后进入类驱动（SET_INTERFACE、类特有请求、SET_IDLE 等视设备类而定）
    end
```

# 抓包文件

[[files/usb.pcapng|U 盘枚举及传输抓包文件]]

## 说明

- **未体现**：`GET_STATUS`、`SET_INTERFACE`、HID `SET_IDLE`、MS OS 描述符、高速 Split 等；均为同类控制传输或总线扩展事务，可接在 **SET_CONFIGURATION** 前后。

