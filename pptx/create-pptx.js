const pptxgen = require('pptxgenjs');
const path = require('path');

// Resolve html2pptx from skill location
const html2pptxPath = path.resolve(process.env.USERPROFILE, '.copilot/skills/pptx/scripts/html2pptx.js');
const html2pptx = require(html2pptxPath);

async function createPresentation() {
    const pptx = new pptxgen();
    pptx.layout = 'LAYOUT_16x9';
    pptx.author = 'Eric Hansen';
    pptx.title = 'AI-Assisted Workflow Authoring';
    pptx.subject = 'Bridging Natural Language to Enterprise Integration Artifacts';

    const slidesDir = path.resolve(__dirname, 'slides');
    
    const slideFiles = [
        'slide1-title.html',
        'slide2-problem.html',
        'slide3-related.html',
        'slide4-themes.html',
        'slide5-msft-pattern.html',
        'slide6-architecture.html',
        'slide7-json.html',
        'slide8-validation.html',
        'slide9-demo.html',
        'slide10-takeaways.html',
        'slide11-questions.html'
    ];

    for (const slideFile of slideFiles) {
        const htmlPath = path.join(slidesDir, slideFile);
        console.log(`Processing ${slideFile}...`);
        await html2pptx(htmlPath, pptx);
    }

    const outputPath = path.resolve(__dirname, 'AI-Workflow-Authoring.pptx');
    await pptx.writeFile({ fileName: outputPath });
    console.log(`\nPresentation created: ${outputPath}`);
}

createPresentation().catch(err => {
    console.error('Error creating presentation:', err);
    process.exit(1);
});
