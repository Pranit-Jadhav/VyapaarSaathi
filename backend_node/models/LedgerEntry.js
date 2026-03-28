const mongoose = require('mongoose');

const SalesItemSchema = new mongoose.Schema({
    item: String,
    qty: String,
    price: Number,
    uncertain: { type: Boolean, default: false }
});

const ExpenseItemSchema = new mongoose.Schema({
    type: String,
    amount: Number
});

const LedgerEntrySchema = new mongoose.Schema({
    transcript: String,
    total_profit: Number,
    sales: [SalesItemSchema],
    expenses: [ExpenseItemSchema],
    feedback: {
        clarification_question: String,
        anomaly_alert: String,
        tomorrow_tip: String
    },
    created_at: { type: Date, default: Date.now }
});

module.exports = mongoose.model('LedgerEntry', LedgerEntrySchema);
