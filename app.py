<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ระบบคำนวณและสรุปราคาค่าขนส่ง</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap');
        body {
            font-family: 'Sarabun', sans-serif;
        }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 p-4 md:p-8 min-h-screen">

    <div class="max-w-7xl mx-auto space-y-6">
        
        <!-- Header -->
        <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
            <h1 class="text-2xl font-bold text-slate-900 mb-2">ระบบจัดการและสรุปราคาค่าขนส่ง</h1>
            <p class="text-slate-500 text-sm">ป้อนข้อมูลการเดินทางเพื่อคำนวณตารางราคาและสรุปรายละเอียดรายคัน</p>
        </div>

        <!-- Form Input -->
        <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
            <h2 class="text-lg font-semibold mb-4 text-slate-800 border-b pb-2">เพิ่มข้อมูลการขนส่ง</h2>
            <form id="transportForm" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                <div>
                    <label class="block text-xs font-medium text-slate-600 mb-1">ทะเบียน/เบอร์รถ</label>
                    <input type="text" id="truckId" required placeholder="เช่น 80-1234 หรือ รถ 01" class="w-full p-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-600 mb-1">จำนวนถัง (ถัง)</label>
                    <input type="number" id="drumCount" min="1" required placeholder="0" class="w-full p-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-600 mb-1">ค่าขนส่งรวม (บาท)</label>
                    <input type="number" id="totalCost" min="0" step="0.01" required placeholder="0.00" class="w-full p-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-600 mb-1">หมายเหตุ / เส้นทาง</label>
                    <input type="text" id="note" placeholder="ระบุรายละเอียด (ถ้ามี)" class="w-full p-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none">
                </div>
                <div class="flex items-end">
                    <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium p-2 rounded-lg text-sm transition shadow">
                        + เพิ่มรายการ
                    </button>
                </div>
            </form>
        </div>

        <!-- ตารางที่ 1: ตารางราคาค่าขนส่งและรายละเอียด (แบบแนวนอน) -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="p-4 bg-slate-100 border-b border-slate-200 flex justify-between items-center">
                <div class="flex items-center space-x-2">
                    <h2 class="font-bold text-slate-800">1. ตารางราคาค่าขนส่งและรายละเอียด (รวมทั้งหมด)</h2>
                    <span id="rowCountBadge" class="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full font-medium">0 รายการ</span>
                </div>
                <button onclick="toggleSection('table1Content')" class="text-xs bg-white border border-slate-300 hover:bg-slate-50 text-slate-600 px-3 py-1.5 rounded-md font-medium transition flex items-center gap-1">
                    <span id="btnText1">ย่อ/ซ่อนตาราง</span>
                </button>
            </div>
            
            <div id="table1Content" class="transition-all duration-300">
                <div class="overflow-x-auto">
                    <table class="w-full text-sm text-left text-slate-600">
                        <thead class="text-xs text-slate-700 uppercase bg-slate-50 border-b">
                            <tr>
                                <th class="px-4 py-3">ลำดับ</th>
                                <th class="px-4 py-3">ทะเบียน/เบอร์รถ</th>
                                <th class="px-4 py-3 text-right">จำนวนถัง</th>
                                <th class="px-4 py-3 text-right">ค่าขนส่งรวม (บาท)</th>
                                <th class="px-4 py-3 text-right bg-blue-50/50 text-blue-900">บาท / ถัง</th>
                                <th class="px-4 py-3">หมายเหตุ</th>
                                <th class="px-4 py-3 text-center">จัดการ</th>
                            </tr>
                        </thead>
                        <tbody id="mainTableBody">
                            <tr>
                                <td colspan="7" class="text-center py-6 text-slate-400">ยังไม่มีข้อมูลรายการขนส่ง</td>
                            </tr>
                        </tbody>
                        <tfoot id="mainTableFoot" class="bg-slate-50 font-semibold text-slate-800 border-t hidden">
                            <!-- JS จะเติมผลรวมตรงนี้ -->
                        </tfoot>
                    </table>
                </div>
            </div>
        </div>

        <!-- ตารางที่ 2: ตารางรายละเอียดแนวตั้ง แยกตามเบอร์รถ -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="p-4 bg-slate-100 border-b border-slate-200 flex justify-between items-center">
                <div class="flex items-center space-x-2">
                    <h2 class="font-bold text-slate-800">2. รายละเอียดแบบแนวตั้ง (แยกตามเบอร์รถ)</h2>
                    <span id="truckCountBadge" class="bg-indigo-100 text-indigo-800 text-xs px-2 py-0.5 rounded-full font-medium">0 คัน</span>
                </div>
                <button onclick="toggleSection('table2Content')" class="text-xs bg-white border border-slate-300 hover:bg-slate-50 text-slate-600 px-3 py-1.5 rounded-md font-medium transition flex items-center gap-1">
                    <span id="btnText2">ย่อ/ซ่อนตาราง</span>
                </button>
            </div>

            <div id="table2Content" class="p-4 transition-all duration-300">
                <div id="verticalTablesContainer" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <div class="col-span-full text-center py-6 text-slate-400">
                        ยังไม่มีข้อมูลแยกตามรถ
                    </div>
                </div>
            </div>
        </div>

    </div>

    <script>
        // ข้อมูลหลัก
        let transportData = [];

        // Element Referneces
        const form = document.getElementById('transportForm');
        const mainTableBody = document.getElementById('mainTableBody');
        const mainTableFoot = document.getElementById('mainTableFoot');
        const verticalTablesContainer = document.getElementById('verticalTablesContainer');
        const rowCountBadge = document.getElementById('rowCountBadge');
        const truckCountBadge = document.getElementById('truckCountBadge');

        // ฟังก์ชันฟอร์แมตตัวเลข
        function formatNumber(num) {
            return new Intl.NumberFormat('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num);
        }

        // เพิ่มข้อมูล
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const truckId = document.getElementById('truckId').value.trim();
            const drumCount = parseInt(document.getElementById('drumCount').value);
            const totalCost = parseFloat(document.getElementById('totalCost').value);
            const note = document.getElementById('note').value.trim();

            const newItem = {
                id: Date.now(),
                truckId: truckId,
                drumCount: drumCount,
                totalCost: totalCost,
                costPerDrum: drumCount > 0 ? (totalCost / drumCount) : 0,
                note: note || '-'
            };

            transportData.push(newItem);
            
            // รีเซ็ตฟอร์ม
            form.reset();
            document.getElementById('truckId').focus();

            // อัปเดตการแสดงผล
            renderAll();
        });

        // ลบข้อมูล
        function deleteItem(id) {
            transportData = transportData.filter(item => item.id !== id);
            renderAll();
        }

        // ฟังก์ชันย่อ/ขยายตาราง
        function toggleSection(elementId) {
            const content = document.getElementById(elementId);
            if (content.classList.contains('hidden')) {
                content.classList.remove('hidden');
            } else {
                content.classList.add('hidden');
            }
        }

        // วาดการแสดงผลทั้งหมด
        function renderAll() {
            renderMainTable();
            renderVerticalTables();
        }

        // 1. วาดตารางแนวนอนหลัก (รวมคอลัมน์ บาท/ถัง)
        function renderMainTable() {
            rowCountBadge.textContent = `${transportData.length} รายการ`;

            if (transportData.length === 0) {
                mainTableBody.innerHTML = `
                    <tr>
                        <td colspan="7" class="text-center py-6 text-slate-400">ยังไม่มีข้อมูลรายการขนส่ง</td>
                    </tr>
                `;
                mainTableFoot.classList.add('hidden');
                return;
            }

            let html = '';
            let totalDrums = 0;
            let totalCosts = 0;

            transportData.forEach((item, index) => {
                totalDrums += item.drumCount;
                totalCosts += item.totalCost;

                html += `
                    <tr class="border-b hover:bg-slate-50 transition">
                        <td class="px-4 py-3">${index + 1}</td>
                        <td class="px-4 py-3 font-semibold text-slate-700">${item.truckId}</td>
                        <td class="px-4 py-3 text-right">${item.drumCount.toLocaleString()}</td>
                        <td class="px-4 py-3 text-right">${formatNumber(item.totalCost)}</td>
                        <td class="px-4 py-3 text-right bg-blue-50/30 text-blue-700 font-medium">${formatNumber(item.costPerDrum)}</td>
                        <td class="px-4 py-3 text-slate-500">${item.note}</td>
                        <td class="px-4 py-3 text-center">
                            <button onclick="deleteItem(${item.id})" class="text-red-500 hover:text-red-700 hover:bg-red-50 p-1.5 rounded transition">
                                ลบ
                            </button>
                        </td>
                    </tr>
                `;
            });

            mainTableBody.innerHTML = html;

            // สรุปยอดรวมท้ายตาราง
            const avgCostPerDrum = totalDrums > 0 ? (totalCosts / totalDrums) : 0;
            mainTableFoot.classList.remove('hidden');
            mainTableFoot.innerHTML = `
                <tr>
                    <td colspan="2" class="px-4 py-3 text-right">รวมทั้งสิ้น</td>
                    <td class="px-4 py-3 text-right text-blue-600">${totalDrums.toLocaleString()} ถัง</td>
                    <td class="px-4 py-3 text-right text-blue-600">${formatNumber(totalCosts)} ฿</td>
                    <td class="px-4 py-3 text-right text-blue-700 bg-blue-100/50">${formatNumber(avgCostPerDrum)} ฿</td>
                    <td colspan="2"></td>
                </tr>
            `;
        }

        // 2. วาดตารางแนวตั้ง แยกตามเบอร์รถ
        function renderVerticalTables() {
            // จัดกลุ่มตามเบอร์รถ
            const groupedData = transportData.reduce((acc, item) => {
                if (!acc[item.truckId]) {
                    acc[item.truckId] = [];
                }
                acc[item.truckId].push(item);
                return acc;
            }, {});

            const truckKeys = Object.keys(groupedData);
            truckCountBadge.textContent = `${truckKeys.length} คัน`;

            if (truckKeys.length === 0) {
                verticalTablesContainer.innerHTML = `
                    <div class="col-span-full text-center py-6 text-slate-400">
                        ยังไม่มีข้อมูลแยกตามรถ
                    </div>
                `;
                return;
            }

            let containerHtml = '';

            truckKeys.forEach(truckId => {
                const items = groupedData[truckId];
                const truckTotalDrums = items.reduce((sum, i) => sum + i.drumCount, 0);
                const truckTotalCost = items.reduce((sum, i) => sum + i.totalCost, 0);
                const truckAvgCostPerDrum = truckTotalDrums > 0 ? (truckTotalCost / truckTotalDrums) : 0;

                containerHtml += `
                    <div class="border border-slate-200 rounded-lg overflow-hidden bg-white shadow-sm hover:shadow transition">
                        <!-- Header การ์ดรถ -->
                        <div class="bg-slate-800 text-white p-3 flex justify-between items-center">
                            <span class="font-bold text-base">🚗 รถ: ${truckId}</span>
                            <span class="text-xs bg-slate-700 px-2 py-0.5 rounded text-slate-200">${items.length} รายการ</span>
                        </div>
                        
                        <!-- ตารางแนวตั้ง -->
                        <div class="p-3 space-y-3">
                            ${items.map((item, idx) => `
                                <div class="border-b border-slate-100 pb-2 last:border-0 text-xs space-y-1">
                                    <div class="flex justify-between font-medium text-slate-500">
                                        <span>เที่ยวที่ ${idx + 1}</span>
                                        <span class="text-slate-400">${item.note}</span>
                                    </div>
                                    <div class="grid grid-cols-2 gap-1 py-1 bg-slate-50 p-2 rounded">
                                        <div><span class="text-slate-500">จำนวนถัง:</span> <strong class="text-slate-700">${item.drumCount.toLocaleString()}</strong> ถัง</div>
                                        <div><span class="text-slate-500">ค่าขนส่ง:</span> <strong class="text-slate-700">${formatNumber(item.totalCost)}</strong> ฿</div>
                                        <div class="col-span-2 text-blue-600 border-t border-slate-200 pt-1 mt-1">
                                            <span>เฉลี่ย:</span> <strong>${formatNumber(item.costPerDrum)}</strong> บาท/ถัง
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>

                        <!-- สรุปรวมของรถคันนี้ -->
                        <div class="bg-indigo-50 border-t border-indigo-100 p-3 text-xs space-y-1">
                            <div class="font-bold text-indigo-900 border-b border-indigo-200 pb-1 mb-1">สรุปรวมรถ ${truckId}</div>
                            <div class="flex justify-between text-indigo-800">
                                <span>รวมจำนวนถัง:</span>
                                <strong>${truckTotalDrums.toLocaleString()} ถัง</strong>
                            </div>
                            <div class="flex justify-between text-indigo-800">
                                <span>รวมค่าขนส่ง:</span>
                                <strong>${formatNumber(truckTotalCost)} บาท</strong>
                            </div>
                            <div class="flex justify-between text-indigo-950 font-bold pt-1 border-t border-indigo-200/60">
                                <span>ราคาเฉลี่ย/ถัง:</span>
                                <span class="text-sm text-indigo-600">${formatNumber(truckAvgCostPerDrum)} บาท</span>
                            </div>
                        </div>
                    </div>
                `;
            });

            verticalTablesContainer.innerHTML = containerHtml;
        }
    </script>
</body>
</html>
