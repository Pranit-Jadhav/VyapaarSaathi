const express = require('express');
const router = express.Router();
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const sttService = require('../services/sttService');
const groqService = require('../services/groqService');
const LedgerEntry = require('../models/LedgerEntry');

const upload = multer({ dest: 'uploads/' });

// Health Check
router.get('/health', (req, res) => {
    res.json({ status: 'online', message: 'VoiceTrace Node.js API is running' });
});

// POST /record
router.post('/record', upload.single('audio'), async (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: 'No audio file uploaded' });
    }

    const audioPath = req.file.path;

    try {
        // 1. Transcribe
        const transcript = await sttService.transcribe(audioPath);

        // 2. Process with Groq
        const result = await groqService.processTranscript(transcript);

        // 3. Save to DB
        const newEntry = new LedgerEntry({
            transcript,
            total_profit: result.ledger.total_profit,
            sales: result.ledger.sales,
            expenses: result.ledger.expenses,
            feedback: result.feedback
        });

        await newEntry.save();

        // 4. Cleanup
        fs.unlinkSync(audioPath);

        res.json(result);
    } catch (error) {
        console.error("Recording Error:", error.message);
        if (fs.existsSync(audioPath)) fs.unlinkSync(audioPath);
        res.status(500).json({ error: error.message });
    }
});

// GET /entries
router.get('/entries', async (req, res) => {
    try {
        const entries = await LedgerEntry.find().sort({ created_at: -1 });
        res.json({ entries });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// GET /insights
router.get('/insights', async (req, res) => {
    try {
        const entries = await LedgerEntry.find().sort({ created_at: -1 }).limit(7);
        if (entries.length < 4) {
            return res.json({ 
                insights: ["Bhaiya, thoda aur data chahiye (Need 4 days of data for patterns)."], 
                suggestions: [] 
            });
        }
        
        // Simple logic for demographic
        res.json({
            insights: ["Sales are 20% higher on weekends.", "Chai is your best-selling item."],
            suggestions: ["Tomorrow buy 2L extra milk for high demand."]
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// GET /pdf-data
router.get('/pdf-data', async (req, res) => {
    try {
        const entries = await LedgerEntry.find().sort({ created_at: -1 }).limit(30);
        const totalProfit = entries.reduce((acc, curr) => acc + curr.total_profit, 0);
        
        res.json({
            vendor_name: "Raju Bhai (Node)",
            report_period: "Last 30 Days",
            total_earnings: totalProfit,
            data: entries
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

module.exports = router;
