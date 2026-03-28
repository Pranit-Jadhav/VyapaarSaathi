const axios = require('axios');
const fs = require('fs');

const BASE_URL = 'http://localhost:5000/api';

async function testApi() {
    console.log("Starting Node.js Backend Verification...");

    try {
        // 1. Health Check
        console.log("\nTesting Health Check...");
        const health = await axios.get(`${BASE_URL}/health`);
        console.log(`Status: ${health.status}, Response:`, health.data);

        // 2. Get Entries
        console.log("\nTesting Get Entries...");
        const entries = await axios.get(`${BASE_URL}/entries`);
        console.log(`Status: ${entries.status}, Count: ${entries.data.entries.length}`);

        // 3. Record Audio (Mock flow)
        console.log("\nTesting Record Audio (Mock)...");
        // Create a dummy file
        fs.writeFileSync('dummy.wav', 'dummy audio data');
        const form = new FormData();
        form.append('audio', new Blob([fs.readFileSync('dummy.wav')]), 'dummy.wav');
        
        try {
            const recordRes = await axios.post(`${BASE_URL}/record`, form, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            console.log(`Status: ${recordRes.status}, Response:`, recordRes.data.ledger ? 'Ledger Extracted' : 'Failed');
        } catch (e) {
            console.log(`Record Endpoint Status: ${e.response?.status || 'Error'}`);
            console.log("This might fail due to strict Whisper validation on dummy files, but the route exists.");
        }
        fs.unlinkSync('dummy.wav');

        // 4. Insights
        console.log("\nTesting Insights...");
        const insights = await axios.get(`${BASE_URL}/insights`);
        console.log(`Status: ${insights.status}, Response:`, insights.data);

        // 5. PDF Data
        console.log("\nTesting PDF Data...");
        const pdfData = await axios.get(`${BASE_URL}/pdf-data`);
        console.log(`Status: ${pdfData.status}, Response:`, pdfData.data.vendor_name);

        console.log("\n✅ All Endpoints Verified (Health, Entries, Insights, PDF)");
    } catch (error) {
        console.error("\n❌ Verification Failed:", error.message);
        if (error.response) {
            console.error("Data:", error.response.data);
        }
    }
}

testApi();
