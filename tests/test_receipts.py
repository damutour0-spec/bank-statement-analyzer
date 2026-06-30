from decimal import Decimal

from statement_analyzer.receipts import transactions_from_receipt_text


def test_parse_icbc_e_receipt_ocr_text():
    text = """
    中国工商银行 网上银行电子回单（补打）
    电子回单号码：0904-1947-9303-1100
    付款人 户名 南昌高新技术产业开发区管理委员会科技创新与经济发展局
    付款人 账号 36001050430058000003
    收款人 户名 江西联益光学有限公司
    收款人 账号 1502209509300227558
    金额 ￥1,061,800.00元
    摘要 第一批产业集群及中小
    交易流水号 98103766
    时间戳 2025-11-25-14.58.49.630717
    """

    transactions = transactions_from_receipt_text(text)

    assert len(transactions) == 1
    txn = transactions[0]
    assert txn.channel == "工商银行电子回单"
    assert txn.expense_amount == Decimal("1061800.00")
    assert txn.income_amount == Decimal("0")
    assert txn.counterparty_name == "江西联益光学有限公司"
    assert txn.transaction_date.strftime("%Y-%m-%d") == "2025-11-25"


def test_parse_abc_transaction_detail_ocr_text():
    text = """
    中国农业银行 账户交易明细
    交易日期：2025-11-26 11:24:14
    付款方 户名 南昌高新技术产业开发区管理委员会科技创新与经济发展局
    收款方 户名 江西联创电子有限公司
    小写 870,700.00
    币种 人民币
    受理渠道 小额支付人行支付中心
    摘要 转存
    交易用途 第一批产业集群及中小企业数字化转型项目资金
    """

    transactions = transactions_from_receipt_text(text)

    assert len(transactions) == 1
    txn = transactions[0]
    assert txn.channel == "农业银行账户交易明细"
    assert txn.expense_amount == Decimal("870700.00")
    assert txn.counterparty_name == "江西联创电子有限公司"
    assert txn.summary == "转存"
    assert txn.transaction_date.strftime("%Y-%m-%d %H:%M:%S") == "2025-11-26 11:24:14"


def test_parse_bocom_receipt_ocr_text():
    text = """
    交通银行 回单
    回单编号 250L171965B2
    回单类型 支付结算
    业务名称 支付汇兑
    借贷标志 借方
    付款人名称 合肥联创光学有限公司
    收款人名称 江西亚年科技有限公司
    币种 人民币
    金额 133,200.00
    摘要 设备采购
    附加信息 设备采购
    记账日期 2025-12-06
    会计流水号 EEW0000YG0070021
    """

    transactions = transactions_from_receipt_text(text)

    assert len(transactions) == 1
    txn = transactions[0]
    assert txn.channel == "交通银行回单"
    assert txn.expense_amount == Decimal("133200.00")
    assert txn.counterparty_name == "江西亚年科技有限公司"
    assert txn.summary == "支付汇兑"
    assert "EEW0000YG0070021" in txn.postscript


def test_parse_bank_acceptance_bill_back_ocr_text():
    text = """
    电子银行承兑汇票背面
    票据号码：5 3183610 0002920260203101050165
    转让背书
    背书人名称 合肥联创光学有限公司
    被背书人名称 江西联创电子有限公司
    背书日期 2026-02-05
    质押 出质人名称 江西联创电子有限公司
    质押权人名称 浙商银行股份有限公司南昌分行
    出质日期 2026-02-05
    """

    transactions = transactions_from_receipt_text(text)

    assert len(transactions) == 1
    txn = transactions[0]
    assert txn.channel == "电子银行承兑汇票"
    assert txn.income_amount == Decimal("0")
    assert txn.expense_amount == Decimal("0")
    assert txn.counterparty_name == "江西联创电子有限公司"
    assert txn.transaction_date.strftime("%Y-%m-%d") == "2026-02-05"
    assert "票据号码" in txn.postscript
